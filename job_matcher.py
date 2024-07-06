import dspy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class SkillExtractor(dspy.Signature):
    """Extract relevant skills from job descriptions and applicant profiles."""
    text = dspy.InputField()
    skills = dspy.OutputField(desc="A list of relevant skills extracted from the input text")

class JobApplicantMatcher(dspy.Signature):
    """Determine the compatibility between a job and an applicant based on skills and other factors."""
    job_description = dspy.InputField()
    applicant_profile = dspy.InputField()
    compatibility_score = dspy.OutputField(desc="A float between 0 and 1 indicating the compatibility")
    reasoning = dspy.OutputField(desc="Explanation of the compatibility score")

class SimilarJobFinder(dspy.Signature):
    """Find similar jobs based on a given job and applicant profile."""
    target_job = dspy.InputField()
    applicant_profile = dspy.InputField()
    job_listings = dspy.InputField()
    similar_jobs = dspy.OutputField(desc="A list of similar jobs with explanations")

import dspy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class JobMatcher:
    def __init__(self):
        self.lm = dspy.OpenAI(model="gpt-3.5-turbo")
        dspy.settings.configure(lm=self.lm)
        
        self.skill_extractor = dspy.Predict(SkillExtractor)
        self.job_applicant_matcher = dspy.Predict(JobApplicantMatcher)
        self.similar_job_finder = dspy.Predict(SimilarJobFinder)
        
        self.vectorizer = TfidfVectorizer(stop_words='english')

    def extract_skills(self, text):
        result = self.skill_extractor(text=text)
        return result.skills

    def calculate_similarity(self, text1, text2):
        if not text1.strip() or not text2.strip():
            return 0.0
        try:
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            return cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        except ValueError:
            return 0.0

    def match_job_applicant(self, job, applicant):
        job_skills = self.extract_skills(job.description)
        applicant_skills = self.extract_skills(applicant.profile)
        
        skill_similarity = self.calculate_similarity(" ".join(job_skills), " ".join(applicant_skills))
        
        result = self.job_applicant_matcher(
            job_description=job.description,
            applicant_profile=applicant.profile
        )
        
        combined_score = (float(result.compatibility_score) + skill_similarity) / 2
        
        return {
            "score": combined_score,
            "reasoning": result.reasoning,
            "skill_similarity": skill_similarity
        }


    def find_similar_jobs(self, target_job, applicant, all_jobs):
        """Find similar jobs based on the target job and applicant profile."""
        job_listings = [f"Job ID: {job.id}, Title: {job.title}, Description: {job.description}" 
                        for job in all_jobs if job.id != target_job.id]
        
        result = self.similar_job_finder(
            target_job=f"Title: {target_job.title}, Description: {target_job.description}",
            applicant_profile=applicant.profile,
            job_listings="\n".join(job_listings)
        )
        
        similar_jobs = []
        for similar_job in result.similar_jobs:
            try:
                job_id = int(similar_job.split("Job ID: ")[1].split(",")[0])
                job = next((j for j in all_jobs if j.id == job_id), None)
                if job:
                    match_result = self.match_job_applicant(job, applicant)
                    similar_jobs.append({
                        "job": job,
                        "score": match_result["score"],
                        "reasoning": match_result["reasoning"]
                    })
            except IndexError:
                continue  # Skip this iteration if the expected format is not met
        
        return sorted(similar_jobs, key=lambda x: x["score"], reverse=True)

    def get_job_recommendations(self, applicant, all_jobs, top_n=5):
        """Get job recommendations for an applicant."""
        recommendations = []
        for job in all_jobs:
            match_result = self.match_job_applicant(job, applicant)
            recommendations.append({
                "job": job,
                "score": match_result["score"],
                "reasoning": match_result["reasoning"]
            })
        
        return sorted(recommendations, key=lambda x: x["score"], reverse=True)[:top_n]

class Applicant:
    def __init__(self, id, profile):
        self.id = id
        self.profile = profile

class Job:
    def __init__(self, id, title, description):
        self.id = id
        self.title = title
        self.description = description