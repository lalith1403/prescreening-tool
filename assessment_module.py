import dspy
import re

class TechnicalAssessment:
    def __init__(self, lm):
        self.lm = lm
        self.assess_code = dspy.ChainOfThought("code: str, language: str -> assessment: str, score: int")
        self.generate_question = dspy.ChainOfThought("job_details: str, difficulty: str -> question: str")

    def evaluate_code(self, code, language):
        result = self.assess_code(code=code, language=language)
        return result.assessment, result.score

    def generate_coding_question(self, job_details, difficulty='medium'):
        result = self.generate_question(job_details=job_details, difficulty=difficulty)
        return result.question

class PersonalityAssessment:
    def __init__(self, lm):
        self.lm = lm
        self.assess_personality = dspy.ChainOfThought("conversation_history: str -> traits: list, assessment: str")

    def evaluate_personality(self, conversation_history):
        result = self.assess_personality(conversation_history=conversation_history)
        return result.traits, result.assessment

class CommunicationAssessment:
    def __init__(self, lm):
        self.lm = lm
        self.assess_communication = dspy.ChainOfThought("conversation_history: str -> clarity: int, coherence: int, assessment: str")

    def evaluate_communication(self, conversation_history):
        result = self.assess_communication(conversation_history=conversation_history)
        return result.clarity, result.coherence, result.assessment

class AssessmentManager:
    def __init__(self, lm):
        self.technical = TechnicalAssessment(lm)
        self.personality = PersonalityAssessment(lm)
        self.communication = CommunicationAssessment(lm)

    def run_assessments(self, user_input, conversation_history, job_details):
        assessments = {}

        # Technical assessment
        if re.search(r'```\w+', user_input):
            code_match = re.search(r'```(\w+)\n([\s\S]+?)\n```', user_input)
            if code_match:
                language, code = code_match.groups()
                assessment, score = self.technical.evaluate_code(code, language)
                assessments['technical'] = {'assessment': assessment, 'score': score}

        # Personality assessment
        traits, personality_assessment = self.personality.evaluate_personality(conversation_history)
        assessments['personality'] = {'traits': traits, 'assessment': personality_assessment}

        # Communication assessment
        clarity, coherence, communication_assessment = self.communication.evaluate_communication(conversation_history)
        assessments['communication'] = {'clarity': clarity, 'coherence': coherence, 'assessment': communication_assessment}

        return assessments