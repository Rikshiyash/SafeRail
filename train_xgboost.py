import numpy as np, pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
import joblib, json
import os

np.random.seed(42)
N = 5000
df = pd.DataFrame({
    'vibration_hz':          np.random.uniform(2, 14, N),
    'strain_microstrain':    np.random.uniform(80, 850, N),
    'temperature_celsius':   np.random.uniform(22, 60, N),
    'humidity_percent':      np.random.uniform(25, 90, N),
    'days_since_inspection': np.random.randint(1, 90, N),
    'zone_encoded':          np.random.randint(0, 4, N),
})
df['risk_score'] = (
    0.35*(df.vibration_hz/14) +
    0.40*(df.strain_microstrain/850) +
    0.25*(df.temperature_celsius/60)
)
df['risk_score'] += np.random.normal(0, 0.05, N)
df['label'] = (df.risk_score > 0.75).astype(int)

df['vibration_spike'] = (df['vibration_hz'] > 11).astype(int)
df['heat_stress'] = (df['temperature_celsius'] > 50).astype(int)
df['combined_stress'] = df['vibration_hz'] * df['strain_microstrain'] / 10000

FEATURES = ['vibration_hz','strain_microstrain','temperature_celsius',
            'humidity_percent','days_since_inspection','zone_encoded',
            'vibration_spike','heat_stress','combined_stress']

X = df[FEATURES]
y = df['label']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

model = xgb.XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    scale_pos_weight=3, eval_metric='auc',
    random_state=42
)
model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)

os.makedirs('ml_models', exist_ok=True)
joblib.dump(model, 'ml_models/model.pkl')
joblib.dump(scaler, 'ml_models/scaler.pkl')
with open('ml_models/features.json','w') as f:
    json.dump(FEATURES, f)

print("Regenerated ML models successfully.")
