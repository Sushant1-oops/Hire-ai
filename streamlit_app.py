"""
Streamlit frontend for AI Semantic Hiring Assistant.
Interactive UI for recruiters to manage candidates and perform semantic search.
"""

import streamlit as st
import requests
import json
import os
import time
from typing import Optional, List
import pandas as pd
from datetime import datetime

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REQUESTS_TIMEOUT = 30


# ==================== PAGE CONFIG ====================
st.set_page_config(
    page_title="AI Semantic Hiring Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main { padding: 0rem 1rem; }
    .stMetric { background-color: #f0f2f6; }
    .stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)


# ==================== SESSION STATE ====================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.user = None


# ==================== API HELPERS ====================
def api_request(method: str, endpoint: str, **kwargs) -> tuple[bool, dict]:
    """Make API request with error handling."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        headers = kwargs.get("headers", {})

        if st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"

        kwargs["headers"] = headers
        kwargs["timeout"] = REQUESTS_TIMEOUT

        response = requests.request(method, url, **kwargs)
        response.raise_for_status()

        return True, response.json()

    except requests.exceptions.Timeout:
        return False, {"error": "Request timeout"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "Cannot connect to server"}
    except requests.exceptions.HTTPError as e:
        try:
            return False, e.response.json()
        except:
            return False, {"error": str(e)}
    except Exception as e:
        return False, {"error": str(e)}


# ==================== AUTH PAGES ====================
def login_page():
    """Login page."""
    st.title("🤖 AI Semantic Hiring Assistant")
    st.subheader("Login to Your Account")

    col1, col2 = st.columns([2, 1])

    with col1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", use_container_width=True):
            success, response = api_request(
                "POST",
                "/api/auth/login",
                json={"email": email, "password": password}
            )

            if success and not response.get("error"):
                data = response.get("data", {})
                st.session_state.authenticated = True
                st.session_state.token = data.get("access_token")
                st.session_state.user = data.get("user")
                st.success("✓ Login successful!")
                st.rerun()
            else:
                st.error(response.get("message", "Login failed"))

        st.divider()
        st.write("Don't have an account?")
        show_register = st.checkbox("Create new account", key="show_register")


def register_page():
    """Registration page."""
    # keep session flag so reruns (due to typing) stay on register view
    st.session_state.show_register = True
    st.title("🤖 AI Semantic Hiring Assistant")
    st.subheader("Create New Account")

    first_name = st.text_input("First Name")
    last_name = st.text_input("Last Name")
    email = st.text_input("Email")
    company = st.text_input("Company (optional)")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    password_confirm = st.text_input("Confirm Password", type="password")

    if st.button("Register", use_container_width=True):
        if password != password_confirm:
            st.error("Passwords don't match")
        elif len(password) < 6:
            st.error("Password must be at least 6 characters")
        else:
            success, response = api_request(
                "POST",
                "/api/auth/register",
                json={
                    "email": email,
                    "username": username,
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name,
                    "company": company
                }
            )

            if success and not response.get("error"):
                st.success("✓ Account created and logged in!")
                # store tokens in session and mark authenticated
                token = response.get("data", {}).get("access_token")
                if token:
                    st.session_state.auth_token = token
                    st.session_state.is_authenticated = True
                    st.info("Proceeding to dashboard...")
                    st.rerun()
                else:
                    # fallback: show login form
                    st.info("Registration succeeded; please login.")
                    st.session_state.show_register = False
                    st.rerun()
            else:
                st.error(response.get("message", "Registration failed"))
                # show raw response for debugging
                st.write(response)


# ==================== MAIN APP ====================
def main_app():
    """Main application."""
    # Sidebar
    with st.sidebar:
        st.title("🤖 AI HR Assistant")

        if st.session_state.user:
            st.write(f"**Welcome, {st.session_state.user['first_name']}!**")
            st.write(f"📧 {st.session_state.user['email']}")

        pages = [
            ("📊 Dashboard", "dashboard"),
            ("📄 Resumes", "resumes"),
            ("🔍 Search", "search"),
            ("🤖 AI Tools", "ai_tools"),
        ]

        current_page = st.radio("Navigation", options=[p[0] for p in pages], index=0)
        page_key = next(p[1] for p in pages if p[0] == current_page)

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()

    # Route to page
    if current_page == "📊 Dashboard":
        dashboard_page()
    elif current_page == "📄 Resumes":
        resumes_page()
    elif current_page == "🔍 Search":
        search_page()
    elif current_page == "🤖 AI Tools":
        ai_tools_page()


def dashboard_page():
    """Dashboard showing analytics."""
    st.title("📊 Dashboard")

    success, response = api_request("GET", "/api/dashboard/stats")

    if success and not response.get("error"):
        data = response.get("data", {})

        # Metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("📄 Total Resumes", data.get("total_resumes", 0))

        with col2:
            st.metric("📚 Unique Skills", len(data.get("top_skills", [])))

        with col3:
            avg_exp = data.get("avg_experience", 0)
            st.metric("📅 Avg Experience", f"{avg_exp} years")

        # Top Skills
        if data.get("top_skills"):
            st.subheader("🎯 Top Skills")
            skills_df = pd.DataFrame(data["top_skills"])
            st.bar_chart(skills_df.set_index("skill"))

        # Experience Distribution
        if data.get("experience_distribution"):
            st.subheader("📊 Experience Distribution")
            exp_data = data["experience_distribution"]
            st.bar_chart(exp_data)

        # Recent Searches
        if data.get("recent_searches"):
            st.subheader("🔍 Recent Searches")
            searches_df = pd.DataFrame(data["recent_searches"])
            st.dataframe(searches_df, use_container_width=True)

    else:
        st.error("Failed to load dashboard data")


def delete_resume_callback(resume_id: int):
    """Callback function to delete a resume."""
    success, response = api_request("DELETE", f"/api/resumes/{resume_id}")
    if success:
        st.session_state.resume_deleted = True
        st.session_state.delete_error = False
        st.session_state.deleted_resume_id = resume_id
    else:
        st.session_state.delete_error = True
        st.session_state.resume_deleted = False


def resumes_page():
    """Resume management page."""
    st.title("📄 Resume Management")

    # Initialize session state for deletion
    if "resume_deleted" not in st.session_state:
        st.session_state.resume_deleted = False
    if "delete_error" not in st.session_state:
        st.session_state.delete_error = False
    if "deleted_resume_id" not in st.session_state:
        st.session_state.deleted_resume_id = None

    tab1, tab2 = st.tabs(["Upload Resume", "View Resumes"])

    with tab1:
        st.subheader("Upload New Resume")
        uploaded_file = st.file_uploader("Choose PDF file", type=["pdf"])

        if uploaded_file and st.button("Upload", use_container_width=True):
            with st.spinner("Processing resume..."):
                files = {"file": (uploaded_file.name, uploaded_file.getbuffer())}
                success, response = api_request(
                    "POST",
                    "/api/resumes/upload",
                    files=files
                )

                if success and not response.get("error"):
                    data = response.get("data", {})
                    st.success("✓ Resume uploaded successfully!")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Name:** {data.get('candidate_name', 'N/A')}")
                        st.write(f"**Email:** {data.get('candidate_email', 'N/A')}")
                    with col2:
                        st.write(f"**Experience:** {data.get('experience_years', 'N/A')} years")
                        st.write(f"**Skills:** {len(data.get('skills', []))} found")

                else:
                    st.error(response.get("message", "Upload failed"))

    with tab2:
        st.subheader("Your Resumes")
        
        # Show success/error messages from deletion
        if st.session_state.resume_deleted:
            st.success(f"✓ Resume deleted successfully")
            st.session_state.resume_deleted = False
            st.session_state.deleted_resume_id = None
            # Force page refresh
            time.sleep(1)
            st.rerun()
        if st.session_state.delete_error:
            st.error("Failed to delete resume")
            st.session_state.delete_error = False
        
        success, response = api_request("GET", "/api/resumes")

        if success and not response.get("error"):
            resumes = response.get("data", [])

            if resumes:
                for resume in resumes:
                    with st.expander(f"📄 {resume['candidate_name']} - {resume['candidate_email']}"):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**Experience:** {resume['experience_years']} years")
                            st.write(f"**Added:** {resume['created_at']}")

                        with col2:
                            skills = resume.get("skills", [])
                            st.write(f"**Skills:** {', '.join(skills[:5])}")
                            if len(skills) > 5:
                                st.write(f"...and {len(skills) - 5} more")

                        st.button(
                            "Delete",
                            key=f"delete_{resume['id']}",
                            on_click=delete_resume_callback,
                            args=(resume['id'],)
                        )
            else:
                st.info("No resumes uploaded yet")

        else:
            st.error("Failed to load resumes")


def search_page():
    """Semantic search page."""
    st.title("🔍 Semantic Search")

    col1, col2 = st.columns(2)

    with col1:
        query = st.text_area(
            "Job Description or Requirements",
            height=150,
            placeholder="Paste job description or requirements..."
        )

    with col2:
        skills_input = st.text_area(
            "Required Skills (one per line)",
            height=150,
            placeholder="Python\nDjango\nPostgreSQL"
        )

        min_experience = st.number_input("Minimum Experience (years)", min_value=0, value=0)
        top_k = st.slider("Top Results", min_value=1, max_value=20, value=5)

    if st.button("🔍 Search", use_container_width=True):
        if not query or not skills_input:
            st.error("Please fill in all fields")
        else:
            with st.spinner("Searching candidates..."):
                required_skills = [s.strip() for s in skills_input.split("\n") if s.strip()]

                success, response = api_request(
                    "POST",
                    "/api/search",
                    json={
                        "query": query,
                        "required_skills": required_skills,
                        "min_experience": min_experience,
                        "top_k": top_k
                    }
                )

                if success and not response.get("error"):
                    results = response.get("data", [])

                    if results:
                        st.success(f"✓ Found {len(results)} candidates")

                        # Results table
                        results_df = pd.DataFrame([
                            {
                                "Rank": r["rank"],
                                "Name": r["candidate_name"],
                                "Email": r["candidate_email"],
                                "Semantic Score": round(r["semantic_similarity"], 3),
                                "Experience Match": round(r["experience_match"], 3),
                                "Skill Overlap": round(r["skill_overlap"], 3),
                                "Final Score": round(r["final_score"], 3),
                                "Recommendation": r["recommendation"]
                            }
                            for r in results
                        ])

                        st.dataframe(results_df, use_container_width=True)

                        # Detail view
                        st.subheader("Candidate Details")
                        selected_idx = st.selectbox(
                            "Select candidate",
                            range(len(results)),
                            format_func=lambda i: f"{results[i]['candidate_name']} ({results[i]['recommendation']})"
                        )

                        if selected_idx is not None:
                            candidate = results[selected_idx]
                            col1, col2, col3 = st.columns(3)

                            with col1:
                                st.metric("Semantic Similarity", candidate["semantic_similarity"])
                            with col2:
                                st.metric("Experience Match", candidate["experience_match"])
                            with col3:
                                st.metric("Skill Overlap", candidate["skill_overlap"])

                            st.info(f"**Recommendation:** {candidate['recommendation']}")

                    else:
                        st.warning("No candidates found matching criteria")

                else:
                    st.error(response.get("message", "Search failed"))


def ai_tools_page():
    """AI features page."""
    st.title("🤖 AI Tools")

    tool = st.radio(
        "Select AI Feature",
        ["Match Analysis", "Interview Questions", "Outreach Email", "Job Description"],
        horizontal=True
    )

    # Get user resumes for selection
    success, response = api_request("GET", "/api/resumes")
    resumes = response.get("data", []) if success else []

    if not resumes and tool != "Job Description":
        st.warning("Please upload resumes first")
        return

    if tool == "Match Analysis":
        st.subheader("🎯 Candidate-Job Match Analysis")

        resume_name = st.selectbox(
            "Select Candidate",
            [f"{r['candidate_name']} ({r['candidate_email']})" for r in resumes],
            key="match_resume"
        )

        if resume_name:
            selected_resume = resumes[[f"{r['candidate_name']} ({r['candidate_email']})" for r in resumes].index(resume_name)]
            resume_id = selected_resume['id']

            job_desc = st.text_area(
                "Job Description",
                height=200,
                placeholder="Paste job description..."
            )

            if st.button("Analyze Match", use_container_width=True):
                if not job_desc:
                    st.error("Please enter job description")
                else:
                    with st.spinner("Analyzing..."):
                        success, response = api_request(
                            "POST",
                            "/api/ai/analyze-match",
                            json={"resume_id": resume_id, "job_description": job_desc}
                        )

                        if success and not response.get("error"):
                            data = response.get("data", {})

                            col1, col2 = st.columns(2)

                            with col1:
                                st.metric("Match Score", data.get("match_score", 0))
                                st.info(f"**Recommendation:** {data.get('recommendation')}")

                            with col2:
                                st.write("**Explanation:**")
                                st.write(data.get("explanation", ""))

                            col1, col2 = st.columns(2)

                            with col1:
                                st.write("**Strengths:**")
                                for strength in data.get("strengths", []):
                                    st.write(f"✓ {strength}")

                            with col2:
                                st.write("**Weaknesses:**")
                                for weakness in data.get("weaknesses", []):
                                    st.write(f"✗ {weakness}")

                            if data.get("missing_skills"):
                                st.write("**Missing Skills:**")
                                for skill in data.get("missing_skills", []):
                                    st.write(f"⚠️ {skill}")

    elif tool == "Interview Questions":
        st.subheader("❓ Generate Interview Questions")

        resume_name = st.selectbox(
            "Select Candidate",
            [f"{r['candidate_name']} ({r['candidate_email']})" for r in resumes],
            key="questions_resume"
        )

        if resume_name:
            selected_resume = resumes[[f"{r['candidate_name']} ({r['candidate_email']})" for r in resumes].index(resume_name)]
            resume_id = selected_resume['id']
            
            # Show auto-detected experience level based on resume
            exp_years = selected_resume.get('experience_years', 0) or 0
            if exp_years < 2:
                auto_level = "Fresher"
            elif exp_years < 5:
                auto_level = "Intermediate"
            else:
                auto_level = "Experienced"
            
            st.info(f"📊 Auto-detected Level: **{auto_level}** ({exp_years} years experience)")

            job_title = st.text_input("Job Title")
            
            # Allow override of candidate level
            candidate_level = st.selectbox(
                "Candidate Level (or use auto-detected)",
                ["Auto-detect", "Fresher", "Intermediate", "Experienced"],
                index=0
            )

            if st.button("Generate Questions", use_container_width=True):
                if not job_title:
                    st.error("Please enter job title")
                else:
                    with st.spinner("Generating..."):
                        payload = {
                            "resume_id": resume_id,
                            "job_title": job_title
                        }
                        # Only send level if not auto-detect
                        if candidate_level != "Auto-detect":
                            payload["candidate_level"] = candidate_level.lower()
                        
                        success, response = api_request(
                            "POST",
                            "/api/ai/generate-questions",
                            json=payload
                        )

                        if success and not response.get("error"):
                            data = response.get("data", {})

                            col1, col2 = st.columns(2)

                            with col1:
                                st.write("**Technical Questions:**")
                                for q in data.get("technical_questions", []):
                                    st.write(f"• {q}")

                            with col2:
                                st.write("**Behavioral Questions:**")
                                for q in data.get("behavioral_questions", []):
                                    st.write(f"• {q}")

                            st.write("**Practical Tasks:**")
                            for task in data.get("practical_tasks", []):
                                st.write(f"• {task}")

                        else:
                            st.error("Failed to generate questions")

    elif tool == "Outreach Email":
        st.subheader("📧 Generate Outreach Email")

        resume_name = st.selectbox(
            "Select Candidate",
            [f"{r['candidate_name']} ({r['candidate_email']})" for r in resumes],
            key="email_resume"
        )

        if resume_name:
            selected_resume = resumes[[f"{r['candidate_name']} ({r['candidate_email']})" for r in resumes].index(resume_name)]
            resume_id = selected_resume['id']

            job_title = st.text_input("Job Title", key="email_job")
            email_type = st.selectbox("Email Type", ["interview_invite", "rejection", "cold_outreach"])
            company_name = st.text_input("Company Name (optional)")
            
            # Interview details (only show if interview_invite is selected)
            if email_type == "interview_invite":
                st.write("**Interview Details (optional):**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    interview_date = st.text_input("Date", placeholder="e.g., March 5, 2026", key="interview_date")
                with col2:
                    interview_time = st.text_input("Time", placeholder="e.g., 2:00 PM", key="interview_time")
                with col3:
                    interview_location = st.text_input("Location", placeholder="e.g., Conference Room A", key="interview_location")
            else:
                interview_date = None
                interview_time = None
                interview_location = None

            if st.button("Generate Email", use_container_width=True):
                if not job_title:
                    st.error("Please enter job title")
                else:
                    with st.spinner("Generating..."):
                        payload = {
                            "resume_id": resume_id,
                            "job_title": job_title,
                            "email_type": email_type,
                            "company_name": company_name
                        }
                        # Add interview details only if provided
                        if email_type == "interview_invite":
                            if interview_date:
                                payload["interview_date"] = interview_date
                            if interview_time:
                                payload["interview_time"] = interview_time
                            if interview_location:
                                payload["interview_location"] = interview_location
                        
                        success, response = api_request(
                            "POST",
                            "/api/ai/generate-email",
                            json=payload
                        )

                        if success and not response.get("error"):
                            data = response.get("data", {})

                            with st.container(border=True):
                                st.write("**Subject:**")
                                st.code(data.get("subject_line", ""))

                                st.write("**Email Body:**")
                                st.write(data.get("email_body", ""))

                        else:
                            st.error("Failed to generate email")

    elif tool == "Job Description":
        st.subheader("📝 Generate Job Description")

        job_title = st.text_input("Job Title")
        job_desc_short = st.text_area(
            "Brief Description",
            height=100,
            placeholder="Summarize the role in 1-2 sentences..."
        )
        company_name = st.text_input("Company Name (optional)")

        skills_input = st.text_area(
            "Required Skills (one per line)",
            height=100,
            placeholder="Python\nDjango\nPostgreSQL"
        )

        if st.button("Generate Job Description", use_container_width=True):
            if not job_title or not job_desc_short or not skills_input:
                st.error("Please fill in required fields")
            else:
                with st.spinner("Generating..."):
                    required_skills = [s.strip() for s in skills_input.split("\n") if s.strip()]

                    success, response = api_request(
                        "POST",
                        "/api/ai/generate-job-description",
                        json={
                            "job_title": job_title,
                            # backend expects 'job_shorthand' field
                            "job_shorthand": job_desc_short,
                            "required_skills": required_skills,
                            "company_name": company_name
                        }
                    )

                    if success and not response.get("error"):
                        data = response.get("data", {})

                        with st.container(border=True):
                            st.write("**Job Description:**")
                            st.write(data.get("job_description", ""))

                            col1, col2 = st.columns(2)

                            with col1:
                                st.write("**Required Skills:**")
                                for skill in data.get("required_skills", []):
                                    st.write(f"• {skill}")

                            with col2:
                                st.write("**Nice-to-Have Skills:**")
                                for skill in data.get("nice_to_have_skills", []):
                                    st.write(f"• {skill}")

                    else:
                        st.error("Failed to generate job description")


# ==================== MAIN ====================
def main():
    """Main entry point."""
    # Check if already authenticated
    if not st.session_state.authenticated:
        # Show login or register
        show_register = st.query_params.get("register", ["false"])[0] == "true"

        if show_register or st.session_state.get("show_register", False):
            register_page()
        else:
            login_page()
    else:
        main_app()


if __name__ == "__main__":
    main()
