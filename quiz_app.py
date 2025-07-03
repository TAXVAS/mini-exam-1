import streamlit as st

# Password protection
def check_password():
    """Επιστρέφει True αν ο χρήστης έχει τον σωστό κωδικό"""
    def password_entered():
        if st.session_state["PASSWORD"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Δεν αποθηκεύουμε τον κωδικό
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        # Πρώτη φορά που τρέχει, ζητάμε κωδικό
        st.text_input("Κωδικός Πρόσβασης", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Λάθος κωδικός, ζητάμε ξανά
        st.text_input("Κωδικός Πρόσβασης", type="password", on_change=password_entered, key="password")
        st.error("😕 Λάθος κωδικός")
        return False
    else:
        # Σωστός κωδικός
        return True

if not check_password():
    st.stop()  # Δεν συνεχίζουμε αν ο κωδικός είναι λάθος

import streamlit as st
import pandas as pd
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import os
import tempfile

# Initialize session state
if 'questions_df' not in st.session_state:
    st.session_state.questions_df = pd.DataFrame()
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'answers' not in st.session_state:
    st.session_state.answers = {}
if 'wrong_questions' not in st.session_state:
    st.session_state.wrong_questions = []
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.now()
if 'time_per_question' not in st.session_state:
    st.session_state.time_per_question = 60  # Default 60 seconds per question
if 'time_left' not in st.session_state:
    st.session_state.time_left = st.session_state.time_per_question
if 'total_time' not in st.session_state:
    st.session_state.total_time = 0
if 'user' not in st.session_state:
    st.session_state.user = "User1"  # Default user, can be changed

# Function to load questions from CSV
def load_questions(uploaded_file):
    return pd.read_csv(uploaded_file)

# Function to reset quiz
def reset_quiz():
    st.session_state.current_index = 0
    st.session_state.answers = {}
    st.session_state.wrong_questions = []
    st.session_state.start_time = datetime.now()
    st.session_state.time_left = st.session_state.time_per_question
    st.session_state.total_time = 0

# Function to create PDF for wrong answers
def create_pdf(wrong_questions):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Wrong Answers Report", ln=True, align='C')
    for i, q in enumerate(wrong_questions):
        pdf.cell(200, 10, txt=f"Question {i+1}: {q['question']}", ln=True)
        pdf.cell(200, 10, txt=f"Your answer: {q['user_answer']}", ln=True)
        pdf.cell(200, 10, txt=f"Correct answer: {q['correct_answer']}", ln=True)
        pdf.cell(200, 10, txt=f"Explanation: {q['explanation']}", ln=True)
        pdf.ln(5)
    return pdf.output(dest='S').encode('latin1')

# Function to save results to Google Sheets
def save_to_gsheet(question, difficulty, correct, time_spent):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("Quiz_Results").sheet1
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            st.session_state.user,
            question,
            difficulty,
            "YES" if correct else "NO",
            time_spent
        ]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")

# Streamlit app layout
st.title("Project Management Quiz App")

# Upload CSV
uploaded_file = st.file_uploader("Upload Questions (CSV)", type="csv")
if uploaded_file and st.session_state.questions_df.empty:
    st.session_state.questions_df = load_questions(uploaded_file)
    reset_quiz()

# User name input
st.session_state.user = st.text_input("Enter your name", st.session_state.user)

# Difficulty filter
if not st.session_state.questions_df.empty:
    difficulty_options = ["All"] + list(st.session_state.questions_df['difficulty'].unique())
    selected_difficulty = st.sidebar.selectbox("Filter by Difficulty", difficulty_options)
    if selected_difficulty != "All":
        filtered_df = st.session_state.questions_df[st.session_state.questions_df['difficulty'] == selected_difficulty]
    else:
        filtered_df = st.session_state.questions_df
    # Option to retry only wrong answers
    retry_wrong = st.sidebar.checkbox("Retry wrong answers only")
    if retry_wrong and st.session_state.wrong_questions:
        filtered_df = pd.DataFrame(st.session_state.wrong_questions)
        st.sidebar.write(f"Retrying {len(filtered_df)} wrong questions")
    # Start quiz button
    if st.button("Start Quiz"):
        reset_quiz()
        st.experimental_rerun()
    # Timer and question display
    if not filtered_df.empty and st.session_state.current_index < len(filtered_df):
        question_row = filtered_df.iloc[st.session_state.current_index]
        st.header(f"Question {st.session_state.current_index+1}/{len(filtered_df)}")
        st.subheader(question_row['question'])
        options = [question_row['option_a'], question_row['option_b'], question_row['option_c'], question_row['option_d']]
        user_choice = st.radio("Options:", options, key=f"q{st.session_state.current_index}")
        # Timer
        if 'timer_start' not in st.session_state:
            st.session_state.timer_start = time.time()
        elapsed = time.time() - st.session_state.timer_start
        st.session_state.time_left = max(0, st.session_state.time_per_question - int(elapsed))
        time_progress = st.session_state.time_left / st.session_state.time_per_question
        st.progress(time_progress, text=f"⏳ Time left: {st.session_state.time_left} seconds")
        # Submit button
        if st.button("Submit Answer"):
            st.session_state.answers[st.session_state.current_index] = user_choice
            # Check if answer is correct
            correct_answer = options[int(ord(question_row['correct_answer']) - ord('A'))]
            is_correct = user_choice == correct_answer
            time_spent = st.session_state.time_per_question - st.session_state.time_left
            st.session_state.total_time += time_spent
            # Save to Google Sheets
            save_to_gsheet(question_row['question'], question_row['difficulty'], is_correct, time_spent)
            # If wrong, add to wrong_questions
            if not is_correct:
                st.session_state.wrong_questions.append({
                    "question": question_row['question'],
                    "user_answer": user_choice,
                    "correct_answer": correct_answer,
                    "explanation": question_row['explanation'],
                    "difficulty": question_row['difficulty']
                })
            # Move to next question or end
            st.session_state.current_index += 1
            st.session_state.timer_start = time.time()
            st.session_state.time_left = st.session_state.time_per_question
            st.experimental_rerun()
        # Time's up
        if st.session_state.time_left <= 0:
            st.error("Time's up! Moving to next question.")
            st.session_state.answers[st.session_state.current_index] = "Time's up"
            st.session_state.wrong_questions.append({
                "question": question_row['question'],
                "user_answer": "Time's up",
                "correct_answer": options[int(ord(question_row['correct_answer']) - ord('A'))],
                "explanation": question_row['explanation'],
                "difficulty": question_row['difficulty']
            })
            st.session_state.current_index += 1
            st.session_state.timer_start = time.time()
            st.session_state.time_left = st.session_state.time_per_question
            time.sleep(2)
            st.experimental_rerun()
    # Show results at the end
    elif st.session_state.current_index >= len(filtered_df) and len(filtered_df) > 0:
        st.header("Quiz Completed!")
        correct_count = sum([1 for i, ans in st.session_state.answers.items()] )
        if ans != "Time's up" and ans == filtered_df.iloc[i]['option_' + filtered_df.iloc[i]['correct_answer'].lower()]:     
            total_questions = len(filtered_df)
        st.subheader(f"Score: {correct_count}/{total_questions} ({correct_count/total_questions*100:.1f}%)")
        st.write(f"Total time: {st.session_state.total_time} seconds")
        # Show wrong answers with explanations
        if st.session_state.wrong_questions:
            st.subheader("Wrong Answers")
            for i, q in enumerate(st.session_state.wrong_questions):
                st.write(f"**Question {i+1}:** {q['question']}")
                st.write(f"**Your answer:** {q['user_answer']}")
                st.write(f"**Correct answer:** {q['correct_answer']}")
                st.write(f"**Explanation:** {q['explanation']}")
                st.divider()
            # Download PDF button
            pdf_data = create_pdf(st.session_state.wrong_questions)
            st.download_button("Download Wrong Answers as PDF", pdf_data, "wrong_answers.pdf", "application/pdf")
        # Show Google Sheets logging status
        st.success("Results have been saved to Google Sheets.")
# No questions loaded
else:
    st.info("Please upload a CSV file with questions to begin.")
