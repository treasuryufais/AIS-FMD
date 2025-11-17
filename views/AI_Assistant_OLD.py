import streamlit as st
import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from utils import load_committees_df, load_transactions_df, load_terms_df, load_committee_budgets_df
from components import apply_nav_title
import re

# Initialize UI
apply_nav_title()
st.title("🤖 AI Financial Assistant")
st.markdown("Ask questions about AIS financial data and get instant insights!")

# Load all data
@st.cache_data(ttl=300)
def load_all_data():
    """Load all financial data tables"""
    return {
        'committees': load_committees_df(),
        'transactions': load_transactions_df(),
        'terms': load_terms_df(),
        'budgets': load_committee_budgets_df()
    }

def prepare_data_context(data: dict) -> str:
    """Create comprehensive data context with full table information"""
    
    df_committees = data['committees']
    df_transactions = data['transactions']
    df_terms = data['terms']
    df_budgets = data['budgets']
    
    # Convert dates for proper filtering
    df_transactions['transaction_date'] = pd.to_datetime(df_transactions['transaction_date'])
    df_terms['start_date'] = pd.to_datetime(df_terms['start_date'])
    df_terms['end_date'] = pd.to_datetime(df_terms['end_date'])
    
    context = f"""
# AIS Financial Database Schema and Complete Data

## DATABASE SCHEMA

### 1. COMMITTEES TABLE
Columns:
- CommitteeID (int): Unique identifier for each committee
- Committee_Name (text): Name of the committee (e.g., "Marketing", "Membership", "Meeting Food")
- Committee_Type (text): Either 'committee' or 'executive'

Total committees: {len(df_committees)}

COMPLETE COMMITTEES DATA:
{df_committees.to_string(index=False)}

---

### 2. TERMS TABLE
Columns:
- TermID (text): Unique identifier (e.g., "FA24", "SP25")
- Semester (text): Full semester name (e.g., "Fall 2024", "Spring 2025")
- start_date (date): Semester start date
- end_date (date): Semester end date

COMPLETE TERMS DATA:
{df_terms.to_string(index=False)}

---

### 3. COMMITTEE BUDGETS TABLE
Columns:
- committeebudgetid (int): Unique budget allocation ID
- termid (text): References TermID from terms table
- committeeid (int): References CommitteeID from committees table
- budget_amount (numeric): Allocated budget amount

Total budget entries: {len(df_budgets)}

COMPLETE BUDGET DATA:
{df_budgets.to_string(index=False)}

---

### 4. TRANSACTIONS TABLE
Columns:
- transactionid (int): Unique transaction identifier
- transaction_date (date): Date of transaction
- amount (numeric): Transaction amount (positive = income, negative = expense)
- details (text): Transaction description
- budget_category (int): References CommitteeID (can be null)
- purpose (text): Transaction purpose/category (e.g., "Dues", "Merch", "Social Events")
- account (text): Source account - either "Venmo" or contains "Wells" for Wells Fargo

Total transactions: {len(df_transactions)}
Date range: {df_transactions['transaction_date'].min()} to {df_transactions['transaction_date'].max()}

COMPLETE TRANSACTIONS DATA (showing all {len(df_transactions)} transactions):
{df_transactions.to_string(index=False, max_rows=None)}

---

## IMPORTANT FILTERING RULES

1. **Income vs Expenses**: 
   - amount > 0 = INCOME
   - amount < 0 = EXPENSE (use abs() for display)

2. **Date Filtering**: 
   - Use transaction_date for filtering by date
   - Join with terms table to filter by semester

3. **Committee Filtering**:
   - Join transactions.budget_category with committees.CommitteeID
   - Filter committees.Committee_Type = 'committee' for regular committees

4. **Account Filtering**:
   - account LIKE '%Venmo%' for Venmo transactions
   - account LIKE '%Well%' for Wells Fargo transactions

5. **Semester Mapping**:
   - Join on: transactions.transaction_date BETWEEN terms.start_date AND terms.end_date

## EXAMPLE QUERIES YOU CAN ANSWER

1. "Show all transactions over $500" → Filter transactions WHERE abs(amount) > 500
2. "What's the total Venmo income?" → Filter WHERE amount > 0 AND account LIKE '%Venmo%', then SUM
3. "Marketing spending in Fall 2024" → Join committees + terms, filter by semester and committee
4. "Which committee spent the most?" → Group by committee, sum expenses, find max
5. "Uncategorized transactions" → Filter WHERE budget_category IS NULL
6. "Average transaction amount by month" → Extract month from date, group, average

## CALCULATION GUIDELINES

- Always provide exact numbers from the data
- When calculating totals, show the breakdown
- For percentages, show numerator and denominator
- Include date ranges in your responses
- List individual transactions when count is reasonable (<20)
- For larger datasets, provide aggregated summaries with key examples
"""
    
    return context

def get_llm():
    """Initialize the Gemini LLM"""
    try:
        api_key = st.secrets["google"]["api_key"]
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0,
            convert_system_message_to_human=True
        )
    except Exception as e:
        st.error(f"Failed to initialize AI model: {e}")
        return None

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Load data
try:
    data = load_all_data()
    
    # Display data overview in expander
    with st.expander("📊 View Available Data", expanded=False):
        tab1, tab2, tab3, tab4 = st.tabs(["Committees", "Terms", "Budgets", "Recent Transactions"])
        
        with tab1:
            st.dataframe(data['committees'], use_container_width=True)
        
        with tab2:
            st.dataframe(data['terms'], use_container_width=True)
        
        with tab3:
            budgets_display = data['budgets'].merge(
                data['committees'][['CommitteeID', 'Committee_Name']],
                left_on='committeeid', right_on='CommitteeID', how='left'
            ).merge(
                data['terms'][['TermID', 'Semester']],
                left_on='termid', right_on='TermID', how='left'
            )[['Semester', 'Committee_Name', 'budget_amount']]
            st.dataframe(budgets_display, use_container_width=True)
        
        with tab4:
            recent = data['transactions'].sort_values('transaction_date', ascending=False).head(100)
            st.dataframe(recent, use_container_width=True)
            st.caption(f"Showing 100 most recent transactions (Total: {len(data['transactions'])})")
    
    # Example questions
    st.markdown("### 💡 Example Questions")
    examples = [
        "Show all transactions over $500",
        "What's the total income from Venmo in Fall 2025?",
        "Which committee has spent the most this semester?",
        "List all uncategorized transactions",
        "What's the average transaction amount by month?",
        "How much has Marketing committee spent in Fall 2024?",
        "Show me all transactions containing 'merch' in the details"
    ]
    
    cols = st.columns(2)
    for idx, example in enumerate(examples):
        with cols[idx % 2]:
            if st.button(example, key=f"ex_{idx}", use_container_width=True):
                st.session_state.example_clicked = example
    
    # Chat interface
    st.markdown("---")
    
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Handle example button clicks
    if "example_clicked" in st.session_state:
        prompt = st.session_state.example_clicked
        del st.session_state.example_clicked
    else:
        prompt = st.chat_input("Ask a question about AIS finances...")
    
    if prompt:
        # Add user message to chat
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing data..."):
                llm = get_llm()
                if llm:
                    try:
                        # Prepare context with ALL data
                        data_context = prepare_data_context(data)
                        
                        # Create comprehensive prompt
                        full_prompt = f"""You are a financial data analyst AI assistant for the University of Florida's Association for Information Systems (AIS).

You have COMPLETE ACCESS to all financial data including:
- All {len(data['transactions'])} transactions with full details
- All committee information
- All budget allocations
- All semester/term definitions

{data_context}

IMPORTANT INSTRUCTIONS:
1. Use the COMPLETE data provided above to answer questions
2. Always analyze the full transaction list, not just summaries
3. When asked for transactions over a certain amount, check ALL transactions
4. Provide specific transaction details when relevant (date, amount, details)
5. Show your calculations and reasoning
6. If filtering by criteria, show how many transactions match
7. Format currency values with $ and commas (e.g., $1,234.56)
8. Always double-check your numbers against the data provided

USER QUESTION: {prompt}

Provide a detailed, accurate answer based on the complete data above."""
                        
                        response = llm.invoke(full_prompt)
                        answer = response.content
                        
                        st.markdown(answer)
                        st.session_state.chat_history.append({"role": "assistant", "content": answer})
                        
                    except Exception as e:
                        error_msg = f"❌ Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

except Exception as e:
    st.error(f"Failed to load data: {str(e)}")
    st.info("Please check your database connection and try again.")