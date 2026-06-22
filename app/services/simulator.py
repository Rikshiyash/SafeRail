import random

class SensorSimulator:
    @staticmethod
    def simulate_tick(segments: list[dict]) -> list[dict]:
        updated_segments = []
        for segment in segments:
            # Create a copy so we don't modify the original dict unexpectedly
            s = dict(segment)
            s["vibration_hz"] = max(2.0, min(14.0, s["vibration_hz"] + random.uniform(-0.4, 0.4)))
            s["strain_microstrain"] = max(80.0, min(850.0, s["strain_microstrain"] + random.uniform(-15.0, 15.0)))
            s["temperature_celsius"] = max(22.0, min(60.0, s["temperature_celsius"] + random.uniform(-0.8, 0.8)))
            s["humidity_percent"] = max(25.0, min(90.0, s["humidity_percent"] + random.uniform(-1.0, 1.0)))
            
            if random.randint(1, 15) == 1:
                s["vibration_hz"] = min(14.0, s["vibration_hz"] * 1.4)
                
            risk_score = 0.35 * (s["vibration_hz"] / 14.0) + 0.40 * (s["strain_microstrain"] / 850.0) + 0.25 * (s["temperature_celsius"] / 60.0)
            s["risk_score"] = risk_score
            
            if risk_score < 0.45:
                s["risk_tier"] = "safe"
            elif risk_score <= 0.75:
                s["risk_tier"] = "warning"
            else:
                s["risk_tier"] = "critical"
                
            updated_segments.append(s)
            
        return updated_segments
