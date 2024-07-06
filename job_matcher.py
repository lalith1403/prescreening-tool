from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class JobMatcher:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()

    def preprocess_job(self, job):
        return f"{job.title} {job.description}"

    def preprocess_applicant(self, assessments):
        technical_score = assessments.get('technical', {}).get('score', 0)
        personality_traits = ' '.join(assessments.get('personality', {}).get('traits', []))
        communication_score = assessments.get('communication', {}).get('clarity', 0) + assessments.get('communication', {}).get('coherence', 0)
        return f"Technical:{technical_score} {personality_traits} Communication:{communication_score}"

    def match_jobs(self, applicant_assessments, jobs):
        job_texts = [self.preprocess_job(job) for job in jobs]
        applicant_text = self.preprocess_applicant(applicant_assessments)

        all_texts = job_texts + [applicant_text]
        tfidf_matrix = self.vectorizer.fit_transform(all_texts)

        applicant_vector = tfidf_matrix[-1]
        job_vectors = tfidf_matrix[:-1]

        similarities = cosine_similarity(applicant_vector, job_vectors)
        
        job_scores = [(job, float(score)) for job, score in zip(jobs, similarities[0])]
        return sorted(job_scores, key=lambda x: x[1], reverse=True)