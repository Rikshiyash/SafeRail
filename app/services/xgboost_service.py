import joblib
import json
import os
import xgboost as xgb
import numpy as np
from datetime import datetime

class XGBoostService:
    def __init__(self):
        self.ready = False
        try:
            base_dir = "ml_models"
            self.model = joblib.load(os.path.join(base_dir, "model.pkl"))
            self.scaler = joblib.load(os.path.join(base_dir, "scaler.pkl"))
            with open(os.path.join(base_dir, "features.json"), "r") as f:
                self.features = json.load(f)
            
            # Optional SHAP explainer
            shap_path = os.path.join(base_dir, "shap_explainer")
            if os.path.exists(shap_path):
                self.explainer = joblib.load(shap_path)
                
            self.ready = True
        except Exception as e:
            print(f"Failed to load XGBoost model: {e}")

    def _build_vector(self, segment: dict) -> list:
        vector = []
        for feature in self.features:
            if feature == "days_since_inspection":
                last_insp = segment.get("last_inspected")
                days = 0
                if last_insp:
                    try:
                        days = (datetime.utcnow() - datetime.fromisoformat(last_insp)).days
                    except:
                        pass
                vector.append(days)
            elif feature == "zone_encoded":
                zones = ["North Delhi", "South Delhi", "East Corridor", "West Line"]
                z = segment.get("zone", "")
                vector.append(zones.index(z) if z in zones else 0)
            elif feature == "vibration_spike":
                vector.append(int(segment.get("vibration_hz", 0) > 11))
            elif feature == "heat_stress":
                vector.append(int(segment.get("temperature_celsius", 0) > 50))
            elif feature == "combined_stress":
                vector.append(segment.get("vibration_hz", 0) * segment.get("strain_microstrain", 0) / 10000)
            else:
                vector.append(segment.get(feature, 0.0))
        return vector

    def predict(self, segment: dict) -> dict:
        if not self.ready:
            return {}
            
        vector = self._build_vector(segment)
        X = np.array([vector])
        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)[0]
        
        risk_pct = round(proba[1] * 100, 1)
        if risk_pct < 45:
            tier = "safe"
        elif risk_pct < 75:
            tier = "warning"
        else:
            tier = "critical"
            
        return {
            "segment_id": segment.get("segment_id"),
            "risk_percentage": risk_pct,
            "risk_tier": tier,
            "prediction_ts": datetime.utcnow().isoformat()
        }

    def batch_predict(self, segments: list[dict]) -> list[dict]:
        if not self.ready or not segments:
            return []
            
        vectors = [self._build_vector(segment) for segment in segments]
        X = np.array(vectors)
        X_scaled = self.scaler.transform(X)
        probas = self.model.predict_proba(X_scaled)
        
        results = []
        ts = datetime.utcnow().isoformat()
        for idx, segment in enumerate(segments):
            risk_pct = round(probas[idx][1] * 100, 1)
            if risk_pct < 45:
                tier = "safe"
            elif risk_pct < 75:
                tier = "warning"
            else:
                tier = "critical"
            
            results.append({
                "segment_id": segment.get("segment_id"),
                "risk_percentage": risk_pct,
                "risk_tier": tier,
                "prediction_ts": ts
            })
        return results
