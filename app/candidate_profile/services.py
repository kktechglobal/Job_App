class JobPilotService:
    def __init__(self):
        self.users, self.email_index, self.sessions, self.reset_codes = {}, {}, {}, {}
        self.profiles, self.candidate_links = {}, {}
        self.companies, self.company_by_employer, self.company_links = {}, {}, {}
        self.jobs, self.applications, self.job_applications = {}, {}, {}
        self.candidate_applications, self.interviews, self.interview_by_application = {}, {}, {}
        self.cards = {}
        self.next_user_id = self.next_profile_id = self.next_company_id = 1
        self.next_job_id = self.next_application_id = self.next_interview_id = self.next_card_id = 1
        self.next_link_id, self.next_session_id, self.next_reset_code = 1, 1, 100000
        self.skills = ["Python", "FastAPI", "JavaScript", "TypeScript", "React", "SQL", "PostgreSQL", "Docker", "AWS"]




        # Profiles and companies
    def candidate_profile(self, candidate_id: int) -> dict:
        return self.profiles.get(candidate_id) or self._not_found("Profile not found")