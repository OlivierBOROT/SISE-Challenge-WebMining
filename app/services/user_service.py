from app.input_model import InputFeatureBuilder
from app.input_model import InputModelManager
from app.schemas import UserSession, MouseBehaviorBatch, DetectionResult

class UserService:

    sessions: dict[str, UserSession] = {}
    
    def __init__(self) -> None:
        self.input_feature_builder = InputFeatureBuilder()
        self.input_model_manager = InputModelManager()

    def create_session(self) -> UserSession:
        """
        Create a new user session

        Returns:
            UserSession: Created user session
        """
        s = UserSession()
        self.sessions[s.id] = s
        return s

    def get_session(self, id: str) -> UserSession|None:
        """
        Retrive a user session from its ID

        Args:
            id (str): Session ID

        Returns:
            UserSession
        """
        return self.sessions.get(id)
    
    def predict_bot(self, behaviour_batch: MouseBehaviorBatch, session_id: str) -> DetectionResult:
        """
        Validate features with FeatureSe, run prediction and return results

        Args:
            features (dict): Input features

        Returns:
            dict: Prediction result
        """
        features = self.input_feature_builder.extract(behaviour_batch)
        session = self.get_session(session_id)

        if not session:
            raise IndexError(f"No session found with id: {session_id}")

        result = self.input_model_manager.predict(features)
        session.input_features = features
        session.bot_prediction = result

        return result


    # def predict_behaviour(self, events: list[dict]) -> dict:
    #     """
    #     Validate features with FeatureSe, run prediction and return results

    #     Args:
    #         features (dict): Input features

    #     Returns:
    #         dict: Prediction result
    #     """