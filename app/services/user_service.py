from app.input_model import InputFeatureBuilder, InputModelManager
from app.behavior_model import BehaviourFeatureBuilder, BehaviourModelManager
from app.schemas import UserSession, MouseBehaviorBatch, UserEvents, DetectionResult
import app.utility.storage as storage

class UserService:

    sessions: dict[str, UserSession] = {}
    
    def __init__(self) -> None:
        self.input_feature_builder = InputFeatureBuilder()
        self.input_model_manager = InputModelManager()
        
        self.behaviour_feature_builder = BehaviourFeatureBuilder()
        self.behaviour_model_manager = BehaviourModelManager()

    def create_session(self, id: str|None = None) -> UserSession:
        """
        Create a new user session

        Returns:
            UserSession: Created user session
        """
        if id:
            s = UserSession(id=id)
        else:
            s = UserSession()

        self.sessions[s.id] = s
        return s

    def get_session(self, id: str, fall_back = True) -> UserSession|None:
        """
        Retrive a user session from its ID

        Args:
            id (str): Session ID
            fall_back (bool): Whether to create a session if not found

        Returns:
            UserSession
        """
        session = self.sessions.get(id)

        if not session and fall_back:
            session = self.create_session(id=id)

        return session
    
    def predict_bot(self, behaviour_batch: MouseBehaviorBatch, session_id: str, source: str = "human") -> DetectionResult:
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

        storage.append(features, source=source)

        return result


    def predict_behaviour(self, events: UserEvents, session_id: str) -> int|None:
        """
        Validate features with FeatureSe, run prediction and return results

        Args:
            features (dict): Input features

        Returns:
            int: Prediction label
        """
        session = self.get_session(session_id)
        if not session:
            raise IndexError(f"No session found with id: {session_id}")
        
        window = session.behaviour_window.window(events.events)
        if not window:
            return None

        features = self.behaviour_feature_builder.build(events)
        
        return 0
        result = self.behaviour_model_manager.predict(features)
        session.behaviour_features = features
        session.behaviour_prediction = result

        return result