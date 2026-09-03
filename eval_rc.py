
import sys; sys.stdout.reconfigure(encoding='utf-8')
from src.data.synthetic.generator import SyntheticDataGenerator
from src.features.root_cause_features import add_interactions
from src.models.root_cause_inference import RootCauseInferenceService
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, classification_report
import numpy as np

print('Generating data...')
gen = SyntheticDataGenerator(seed=42)
customers = gen.generate_customers(n=1000)
subscriptions = gen.generate_subscriptions(customers)
payments = gen.generate_payments(customers, subscriptions)
invoices = gen.generate_invoices(subscriptions, payments)

service = RootCauseInferenceService()

# Create dataframe from payments exactly as train script does
import pandas as pd
df = pd.DataFrame([p.__dict__ for p in payments])
df = df[df['status'] == 'failed'].copy()

# Filter out early months like train script? Actually let's just test all.
# Add source_type
df['source_type'] = 'payment'

# Features required for ML fallback (simulate what generate_features does)
df_fb = add_interactions(df.copy())
df_fb['label'] = df['failure_reason']

y_true = []
y_pred = []
y_pred_before = []

explicit_indices = []
ambiguous_indices = []

print('Evaluating...')
for i, row in df_fb.iterrows():
    # True label
    true_label = row['label']
    
    # BEFORE patch (only source_type)
    features_before = {
        'source_type': row['source_type']
    }
    # Add rest of ML features to features_before so ML fallback works!
    for col in df_fb.columns:
        if col not in ['payment_id', 'customer_id', 'subscription_id', 'idempotency_key', 'provider_reference', 'label', 'failure_reason', 'failure_code', 'created_at', 'updated_at', 'occurred_at', '_sa_instance_state']:
            features_before[col] = row[col]
            
    try:
        pred_before, conf, is_det = service.diagnose(features_before, 'dummy_customer_id')
    except Exception as e:
        pred_before = 'UNKNOWN'
        
    y_pred_before.append(pred_before)
    
    # AFTER patch (includes failure_code and failure_reason)
    features_after = features_before.copy()
    features_after['failure_code'] = row['failure_code']
    features_after['failure_reason'] = row['failure_reason']
    
    try:
        pred_after, conf, is_det = service.diagnose(features_after, 'dummy_customer_id')
    except Exception as e:
        pred_after = 'UNKNOWN'
        
    y_pred.append(pred_after)
    y_true.append(true_label)
    
    if row['failure_code'] and row['failure_code'].startswith('ERR_GENERIC'):
        ambiguous_indices.append(len(y_true)-1)
    else:
        explicit_indices.append(len(y_true)-1)

print('--- BEFORE PATCH (Only ML Fallback used) ---')
print(f'Overall Accuracy: {accuracy_score(y_true, y_pred_before):.4f}')
print(f'Macro F1: {f1_score(y_true, y_pred_before, average=\'macro\'):.4f}')

print('\n--- AFTER PATCH (Deterministic + ML Fallback) ---')
print(f'Overall Accuracy: {accuracy_score(y_true, y_pred):.4f}')
print(f'Macro F1: {f1_score(y_true, y_pred, average=\'macro\'):.4f}')

# explicit / ambiguous
y_true_exp = [y_true[i] for i in explicit_indices]
y_pred_exp = [y_pred[i] for i in explicit_indices]

y_true_amb = [y_true[i] for i in ambiguous_indices]
y_pred_amb = [y_pred[i] for i in ambiguous_indices]

print(f'\nExplicit subset accuracy (n={len(y_true_exp)}): {accuracy_score(y_true_exp, y_pred_exp):.4f}')
print(f'Ambiguous subset accuracy (n={len(y_true_amb)}): {accuracy_score(y_true_amb, y_pred_amb):.4f}')

