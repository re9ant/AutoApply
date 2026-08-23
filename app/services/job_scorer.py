import logging
from typing import Dict, List, Tuple
from app.config.settings import settings
from app.models.candidate import CandidateProfile
from app.models.job import (
    CategoryScore,
    ExtractedJobDescription,
    MatchScoreBreakdown,
    WorkplaceType,
)

logger = logging.getLogger(__name__)


class JobScorer:
    """Generalized hybrid deterministic & semantic scoring engine across Tech & Game Dev roles."""

    def __init__(
        self,
        min_auto_apply_score: int = settings.MINIMUM_AUTO_APPLY_SCORE,
        min_review_score: int = settings.MINIMUM_REVIEW_SCORE
    ):
        self.min_auto_apply_score = min_auto_apply_score
        self.min_review_score = min_review_score

    def calculate_match(
        self,
        jd: ExtractedJobDescription,
        profile: CandidateProfile
    ) -> MatchScoreBreakdown:
        """Perform comprehensive match scoring against candidate profile."""
        category_scores: Dict[str, CategoryScore] = {}
        disqualification_reasons: List[str] = []
        strengths: List[str] = []
        gaps: List[str] = []

        # 1. Hard Disqualifier Gate
        disqualified, gate_reasons = self._check_hard_disqualifiers(jd, profile)
        if disqualified:
            disqualification_reasons.extend(gate_reasons)

        # 2. Score Categories
        # Category A: Role & Title Match (Max 25)
        role_score = self._score_role(jd, profile)
        category_scores["Role Match"] = role_score
        if role_score.awarded_points >= 20:
            strengths.append(f"Target role alignment: {jd.title}")

        # Category B: Tech Stack / Framework / Engine Match (Max 20)
        tech_score = self._score_engine_or_frameworks(jd, profile)
        category_scores["Core Tech / Engine Match"] = tech_score
        if tech_score.matched_items:
            strengths.append(f"Verified core technology match: {', '.join(tech_score.matched_items)}")
        if tech_score.missing_items:
            gaps.append(f"Missing core technology requirement: {', '.join(tech_score.missing_items)}")

        # Category C: Programming Languages Match (Max 15)
        lang_score = self._score_languages(jd, profile)
        category_scores["Language Match"] = lang_score
        if lang_score.matched_items:
            strengths.append(f"Primary language match: {', '.join(lang_score.matched_items)}")
        if lang_score.missing_items:
            gaps.append(f"Missing language requirements: {', '.join(lang_score.missing_items)}")

        # Category D: Experience & Seniority Match (Max 15)
        exp_score = self._score_experience(jd, profile)
        category_scores["Experience Match"] = exp_score

        # Category E: Systems, Tools & Domain Relevance (Max 15)
        domain_score = self._score_domain_systems(jd, profile)
        category_scores["Domain & Systems Match"] = domain_score
        if domain_score.matched_items:
            strengths.append(f"Matching technical capabilities: {', '.join(domain_score.matched_items)}")

        # Category F: Workplace & Location Match (Max 10)
        location_score = self._score_location(jd, profile)
        category_scores["Location Match"] = location_score

        # Calculate Total Score
        raw_total = sum(cat.awarded_points for cat in category_scores.values())
        total_score = max(0.0, min(100.0, round(raw_total, 1)))

        # If hard disqualified, cap total score and mark action
        meets_hard_reqs = len(disqualification_reasons) == 0
        if not meets_hard_reqs:
            total_score = min(total_score, 45.0)

        # Decision Action
        if not meets_hard_reqs or total_score < self.min_review_score:
            recommended_action = "REJECT"
        elif total_score >= self.min_auto_apply_score:
            recommended_action = "AUTO_APPLY"
        else:
            recommended_action = "REVIEW_QUEUE"

        summary = (
            f"Overall Match: {total_score}% | Status: {recommended_action}. "
            f"Role '{jd.title}' at {jd.company} matches {len(strengths)} key candidate areas."
        )

        return MatchScoreBreakdown(
            total_score=total_score,
            meets_hard_requirements=meets_hard_reqs,
            disqualification_reasons=disqualification_reasons,
            category_scores=category_scores,
            key_strengths=strengths,
            key_gaps=gaps,
            match_summary=summary,
            recommended_action=recommended_action
        )

    def _check_hard_disqualifiers(
        self,
        jd: ExtractedJobDescription,
        profile: CandidateProfile
    ) -> Tuple[bool, List[str]]:
        reasons = []

        # Visa sponsorship check
        if profile.work_authorization.requires_sponsorship and jd.visa_sponsorship is False:
            reasons.append("Candidate requires visa sponsorship, but job posting explicitly disallows sponsorship.")

        # Seniority mismatch
        candidate_years = len(profile.experience) * 1.0
        if jd.experience_years_min and jd.experience_years_min > (candidate_years + 4):
            reasons.append(
                f"Seniority gap: Job requires {jd.experience_years_min}+ years experience, candidate has ~{candidate_years:.1f} years."
            )

        return len(reasons) > 0, reasons

    def _score_role(self, jd: ExtractedJobDescription, profile: CandidateProfile) -> CategoryScore:
        max_pts = 25.0
        jd_title_lower = jd.title.lower()
        matched = []

        for preferred_role in profile.preferences.roles:
            if preferred_role.lower() in jd_title_lower or jd_title_lower in preferred_role.lower():
                matched.append(preferred_role)

        if matched:
            awarded = max_pts
            reason = f"Job title '{jd.title}' matches preferred target roles: {', '.join(matched)}"
        elif any(term in jd_title_lower for term in ["engineer", "developer", "programmer", "software", "backend", "full stack", "game"]):
            awarded = 20.0
            reason = f"Job title '{jd.title}' is aligned with software and engineering roles."
        else:
            awarded = 8.0
            reason = f"Job title '{jd.title}' does not closely match preferred target roles."

        return CategoryScore(
            category_name="Role Match",
            max_points=max_pts,
            awarded_points=awarded,
            reason=reason,
            matched_items=matched
        )

    def _score_engine_or_frameworks(self, jd: ExtractedJobDescription, profile: CandidateProfile) -> CategoryScore:
        max_pts = 20.0
        candidate_engines = [e.lower() for e in profile.skills.engines]
        candidate_frameworks = [f.lower() for f in profile.skills.frameworks]
        candidate_tools = [t.lower() for t in profile.skills.tools]
        all_tech = candidate_engines + candidate_frameworks + candidate_tools

        # Case 1: Game Dev with specific required engine
        if jd.primary_engines:
            matched = []
            missing = []
            for req_engine in jd.primary_engines:
                is_matched = any(req_engine.lower() in cand_eng for cand_eng in candidate_engines)
                if is_matched:
                    matched.append(req_engine)
                else:
                    missing.append(req_engine)

            if matched:
                awarded = max_pts
                reason = f"Candidate profile verified in required game engine(s): {', '.join(matched)}"
            else:
                awarded = 4.0
                reason = f"Candidate lacks verified primary experience in required engine(s): {', '.join(missing)}"

            return CategoryScore(
                category_name="Core Tech / Engine Match",
                max_points=max_pts,
                awarded_points=awarded,
                reason=reason,
                matched_items=matched,
                missing_items=missing
            )

        # Case 2: General Software / Backend / Fullstack role
        req_tech = jd.tech_stack or []
        if req_tech:
            matched = [t for t in req_tech if any(t.lower() in c or c in t.lower() for c in all_tech)]
            missing = [t for t in req_tech if not any(t.lower() in c or c in t.lower() for c in all_tech)]
            ratio = len(matched) / max(1, len(req_tech))
            awarded = max_pts if ratio >= 0.5 else max(6.0, round(max_pts * ratio, 1))
            reason = f"Candidate matches core frameworks/tools: {', '.join(matched)}" if matched else "General tech stack."
            return CategoryScore(
                category_name="Core Tech / Engine Match",
                max_points=max_pts,
                awarded_points=awarded,
                reason=reason,
                matched_items=matched,
                missing_items=missing
            )

        return CategoryScore(
            category_name="Core Tech / Engine Match",
            max_points=max_pts,
            awarded_points=18.0,
            reason="No restrictive proprietary engine required; standard tech stack applies.",
            matched_items=[]
        )

    def _score_languages(self, jd: ExtractedJobDescription, profile: CandidateProfile) -> CategoryScore:
        max_pts = 15.0
        candidate_langs = [l.lower() for l in profile.skills.languages]
        req_langs = jd.primary_languages or []

        if not req_langs:
            return CategoryScore(
                category_name="Language Match",
                max_points=max_pts,
                awarded_points=15.0,
                reason="General programming languages accepted.",
                matched_items=profile.skills.languages[:2]
            )

        matched = []
        missing = []

        for req_lang in req_langs:
            r_lower = req_lang.lower()
            is_matched = any(r_lower in cand_l or cand_l in r_lower for cand_l in candidate_langs)
            if is_matched:
                matched.append(req_lang)
            else:
                missing.append(req_lang)

        if len(matched) == len(req_langs) and req_langs:
            awarded = max_pts
            reason = f"Candidate has verified skills in all primary required languages: {', '.join(matched)}"
        elif matched:
            awarded = round(max_pts * (len(matched) / len(req_langs)), 1)
            reason = f"Candidate has partial language match ({', '.join(matched)}), missing: {', '.join(missing)}"
        else:
            awarded = 2.0
            reason = f"Candidate does not list required primary languages: {', '.join(missing)}"

        return CategoryScore(
            category_name="Language Match",
            max_points=max_pts,
            awarded_points=awarded,
            reason=reason,
            matched_items=matched,
            missing_items=missing
        )

    def _score_experience(self, jd: ExtractedJobDescription, profile: CandidateProfile) -> CategoryScore:
        max_pts = 15.0
        req_min_exp = jd.experience_years_min or 0

        if req_min_exp <= 1:
            awarded = max_pts
            reason = "Role is entry-level / associate friendly (0-1 years required)."
        elif req_min_exp <= 3:
            awarded = 12.0
            reason = f"Role requires {req_min_exp} years; candidate possesses 1-2 years combined project & industry experience."
        elif req_min_exp <= 5:
            awarded = 6.0
            reason = f"Role requires {req_min_exp} years (mid-level); candidate is slightly junior."
        else:
            awarded = 0.0
            reason = f"Role requires senior level ({req_min_exp}+ years)."

        return CategoryScore(
            category_name="Experience Match",
            max_points=max_pts,
            awarded_points=awarded,
            reason=reason
        )

    def _score_domain_systems(self, jd: ExtractedJobDescription, profile: CandidateProfile) -> CategoryScore:
        max_pts = 15.0
        all_candidate_skills = " ".join(
            profile.skills.game_systems + profile.skills.frameworks + profile.skills.tools
        ).lower()

        matched = []
        target_systems = jd.game_systems if jd.game_systems else jd.tech_stack

        for system in target_systems:
            keywords = system.lower().split()
            if any(kw in all_candidate_skills for kw in keywords if len(kw) > 2):
                matched.append(system)

        if not target_systems:
            awarded = 13.0
            reason = "Standard software engineering domain requirements."
        elif matched:
            ratio = min(1.0, len(matched) / max(1, len(target_systems)))
            awarded = round(max_pts * max(0.6, ratio), 1)
            reason = f"Candidate experience matches {len(matched)} required domain subsystems/tools."
        else:
            awarded = 6.0
            reason = "Partial domain overlap with candidate core skill set."

        return CategoryScore(
            category_name="Domain & Systems Match",
            max_points=max_pts,
            awarded_points=awarded,
            reason=reason,
            matched_items=matched
        )

    def _score_location(self, jd: ExtractedJobDescription, profile: CandidateProfile) -> CategoryScore:
        max_pts = 10.0

        if jd.workplace_type == WorkplaceType.REMOTE:
            return CategoryScore(
                category_name="Location Match",
                max_points=max_pts,
                awarded_points=10.0,
                reason="Job is fully Remote, matching candidate preference."
            )

        jd_loc_lower = jd.location.lower()
        for pref_loc in profile.preferences.locations:
            if pref_loc.lower() in jd_loc_lower or jd_loc_lower in pref_loc.lower():
                return CategoryScore(
                    category_name="Location Match",
                    max_points=max_pts,
                    awarded_points=10.0,
                    reason=f"Job location '{jd.location}' matches candidate preferred location '{pref_loc}'."
                )

        if profile.work_authorization.willing_to_relocate and profile.preferences.allow_onsite:
            return CategoryScore(
                category_name="Location Match",
                max_points=max_pts,
                awarded_points=8.0,
                reason=f"Job is on-site/hybrid at '{jd.location}'; candidate is willing to relocate."
            )

        return CategoryScore(
            category_name="Location Match",
            max_points=max_pts,
            awarded_points=4.0,
            reason=f"Location '{jd.location}' is outside target regions without confirmed relocation."
        )


job_scorer = JobScorer()
