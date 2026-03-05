from app.schemas import UserSession

class UserService:

    sessions: dict[str, UserSession]

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
    
    def predict_bot(self, features: dict) -> dict:
        """
        Validate features with FeatureSe, run prediction and return results

        Args:
            features (dict): Input features

        Returns:
            dict: Prediction result
        """

    def predict_behaviour(self, events: list[dict]) -> dict:
        """
        Validate features with FeatureSe, run prediction and return results

        Args:
            features (dict): Input features

        Returns:
            dict: Prediction result
        """