import dspy

class ModularPrescreeningTool:
    def __init__(self):
        self.lm = dspy.OpenAI(model="gpt-3.5-turbo")
        dspy.settings.configure(lm=self.lm)
        self.generate_response = dspy.ChainOfThought("history: str, user_input: str, job_details: str -> response: str, application_complete: bool, applicant_profile: str")

    def process_interaction(self, history, user_input, job_details):
        result = self.generate_response(history=history, user_input=user_input, job_details=job_details)
        assessment = {
            'application_complete': result.application_complete,
            'applicant_profile': result.applicant_profile
        }
        return result.response, assessment