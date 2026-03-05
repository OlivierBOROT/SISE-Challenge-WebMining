from app.behavior_model import BehaviourFeatureBuilder, BehaviourModelManager
from app.input_model import InputFeatureBuilder, InputModelManager
from app.schemas import (
    BehaviourFeatureSet,
    DetectionResult,
    InputFeatureSet,
    MouseBehaviorBatch,
    UserEvents,
    UserSession,
)
from app.utility.storage import StorageService


class UserService:
    sessions: dict[str, UserSession] = {}
    behaviour_storage: StorageService
    input_storage: StorageService

    def __init__(self) -> None:
        self.input_feature_builder = InputFeatureBuilder()
        self.input_model_manager = InputModelManager()
        self.input_storage = StorageService(
            jsonl_path="features/input_features.jsonl", feature_class=InputFeatureSet
        )

        self.behaviour_feature_builder = BehaviourFeatureBuilder()
        self.behaviour_model_manager = BehaviourModelManager()
        self.behaviour_storage = StorageService(
            jsonl_path="features/behaviour_features.jsonl",
            feature_class=BehaviourFeatureSet,
        )

    def create_session(self, session_id: str | None = None) -> UserSession:
        """
        Create a new user session

        Returns:
            UserSession: Created user session
        """
        if session_id:
            s = UserSession(id=session_id)
        else:
            s = UserSession()

        self.sessions[s.id] = s
        return s

    def get_session(self, session_id: str, fall_back=True) -> UserSession | None:
        """
        Retrive a user session from its ID

        Args:
            session_id (str): Session ID
            fall_back (bool): Whether to create a session if not found

        Returns:
            UserSession
        """
        session = self.sessions.get(session_id)

        if not session and fall_back:
            session = self.create_session(session_id=session_id)

        return session

    def predict_bot(
        self,
        behaviour_batch: MouseBehaviorBatch,
        session_id: str,
        source: str = "human",
    ) -> DetectionResult:
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

        self.input_storage.append(features, source=source)

        return result

    def predict_behaviour(
        self, events: UserEvents, session_id: str, source: str = "human"
    ) -> int | None:
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
        self.behaviour_storage.append(features, source=source)

        result = self.behaviour_model_manager.predict(features)
        session.behaviour_features = features
        session.behaviour_prediction = result

        return result
