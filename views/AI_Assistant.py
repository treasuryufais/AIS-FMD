import streamlit as st
import pandas as pd
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from utils import load_committees_df, load_transactions_df, load_terms_df, load_committee_budgets_df
from components import apply_nav_title
import google.generativeai as genai

# Initialize UI
apply_nav_title()
st.title("🤖 AI Financial Assistant")
st.markdown("Ask questions about AIS financial data and get instant, accurate insights!")

# Load data globally
@st.cache_data(ttl=300)
def load_all_data():
    """Load all financial data tables"""
    df_committees = load_committees_df()
    df_transactions = load_transactions_df()
    df_terms = load_terms_df()
    df_budgets = load_committee_budgets_df()
    
    # Convert dates
    df_transactions['transaction_date'] = pd.to_datetime(df_transactions['transaction_date'])
    df_terms['start_date'] = pd.to_datetime(df_terms['start_date'])
    df_terms['end_date'] = pd.to_datetime(df_terms['end_date'])
    
    return {
        'committees': df_committees,
        'transactions': df_transactions,
        'terms': df_terms,
        'budgets': df_budgets
    }

# Load data
try:
    DATA = load_all_data()
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# ============================================================================
# TOOL FUNCTIONS - These will be called by the AI
# ============================================================================

def filter_transactions_by_amount(
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    transaction_type: Optional[str] = None
) -> str:
    """
    Filter transactions by amount range.
    
    Args:
        min_amount: Minimum absolute amount (optional)
        max_amount: Maximum absolute amount (optional)
        transaction_type: 'income', 'expense', or None for all (optional)
    
    Returns:
        JSON string with filtered transactions
    """
    df = DATA['transactions'].copy()
    df['abs_amount'] = df['amount'].abs()
    
    # Filter by amount
    if min_amount is not None:
        df = df[df['abs_amount'] >= min_amount]
    if max_amount is not None:
        df = df[df['abs_amount'] <= max_amount]
    
    # Filter by type
    if transaction_type == 'income':
        df = df[df['amount'] > 0]
    elif transaction_type == 'expense':
        df = df[df['amount'] < 0]
    
    # Format for output
    result = df[['transactionid', 'transaction_date', 'amount', 'details', 'purpose', 'account']].copy()
    result['transaction_date'] = result['transaction_date'].dt.strftime('%Y-%m-%d')
    
    return json.dumps({
        'count': len(result),
        'total_amount': float(df['abs_amount'].sum()),
        'transactions': result.to_dict('records')
    }, default=str)


def filter_transactions_by_semester(
    semester: str,
    transaction_type: Optional[str] = None
) -> str:
    """
    Filter transactions by semester.
    
    Args:
        semester: Semester name like "Fall 2024", "Spring 2025", etc.
        transaction_type: 'income', 'expense', or None for all (optional)
    
    Returns:
        JSON string with filtered transactions
    """
    df_txn = DATA['transactions'].copy()
    df_terms = DATA['terms']
    
    # Find semester dates
    term_row = df_terms[df_terms['Semester'].str.lower() == semester.lower()]
    if term_row.empty:
        return json.dumps({'error': f'Semester "{semester}" not found. Available: {", ".join(df_terms["Semester"].tolist())}'})
    
    start_date = term_row.iloc[0]['start_date']
    end_date = term_row.iloc[0]['end_date']
    
    # Filter by date range
    df_txn = df_txn[
        (df_txn['transaction_date'] >= start_date) &
        (df_txn['transaction_date'] <= end_date)
    ]
    
    # Filter by type
    if transaction_type == 'income':
        df_txn = df_txn[df_txn['amount'] > 0]
    elif transaction_type == 'expense':
        df_txn = df_txn[df_txn['amount'] < 0]
    
    # Format
    result = df_txn[['transactionid', 'transaction_date', 'amount', 'details', 'purpose', 'account']].copy()
    result['transaction_date'] = result['transaction_date'].dt.strftime('%Y-%m-%d')
    
    return json.dumps({
        'semester': semester,
        'date_range': f'{start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}',
        'count': len(result),
        'total_income': float(df_txn[df_txn['amount'] > 0]['amount'].sum()) if transaction_type != 'expense' else 0,
        'total_expenses': float(df_txn[df_txn['amount'] < 0]['amount'].abs().sum()) if transaction_type != 'income' else 0,
        'transactions': result.to_dict('records')
    }, default=str)


def filter_transactions_by_account(
    account_type: str,
    semester: Optional[str] = None
) -> str:
    """
    Filter transactions by account type (Venmo or Wells Fargo).
    
    Args:
        account_type: 'venmo' or 'wells' (case insensitive)
        semester: Optional semester filter like "Fall 2024"
    
    Returns:
        JSON string with filtered transactions
    """
    df_txn = DATA['transactions'].copy()
    
    # Filter by account
    if 'venmo' in account_type.lower():
        df_txn = df_txn[df_txn['account'].str.contains('Venmo', case=False, na=False)]
    elif 'well' in account_type.lower():
        df_txn = df_txn[df_txn['account'].str.contains('Well', case=False, na=False)]
    else:
        return json.dumps({'error': f'Unknown account type: {account_type}. Use "venmo" or "wells"'})
    
    # Optional semester filter
    if semester:
        df_terms = DATA['terms']
        term_row = df_terms[df_terms['Semester'].str.lower() == semester.lower()]
        if not term_row.empty:
            start_date = term_row.iloc[0]['start_date']
            end_date = term_row.iloc[0]['end_date']
            df_txn = df_txn[
                (df_txn['transaction_date'] >= start_date) &
                (df_txn['transaction_date'] <= end_date)
            ]
    
    # Format
    result = df_txn[['transactionid', 'transaction_date', 'amount', 'details', 'purpose', 'account']].copy()
    result['transaction_date'] = result['transaction_date'].dt.strftime('%Y-%m-%d')
    
    return json.dumps({
        'account_type': account_type,
        'semester': semester if semester else 'all time',
        'count': len(result),
        'total_income': float(df_txn[df_txn['amount'] > 0]['amount'].sum()),
        'total_expenses': float(df_txn[df_txn['amount'] < 0]['amount'].abs().sum()),
        'transactions': result.to_dict('records')
    }, default=str)


def get_committee_spending(
    committee_name: Optional[str] = None,
    semester: Optional[str] = None
) -> str:
    """
    Get spending breakdown by committee.
    
    Args:
        committee_name: Specific committee name (optional, returns all if None)
        semester: Filter by semester (optional)
    
    Returns:
        JSON string with spending data
    """
    df_txn = DATA['transactions'].copy()
    df_committees = DATA['committees']
    
    # Filter expenses only
    df_txn = df_txn[df_txn['amount'] < 0].copy()
    df_txn['amount'] = df_txn['amount'].abs()
    
    # Optional semester filter
    if semester:
        df_terms = DATA['terms']
        term_row = df_terms[df_terms['Semester'].str.lower() == semester.lower()]
        if not term_row.empty:
            start_date = term_row.iloc[0]['start_date']
            end_date = term_row.iloc[0]['end_date']
            df_txn = df_txn[
                (df_txn['transaction_date'] >= start_date) &
                (df_txn['transaction_date'] <= end_date)
            ]
    
    # Merge with committee names
    df_txn = df_txn.merge(
        df_committees[['CommitteeID', 'Committee_Name']],
        left_on='budget_category',
        right_on='CommitteeID',
        how='left'
    )
    
    # Optional committee filter
    if committee_name:
        df_txn = df_txn[df_txn['Committee_Name'].str.lower() == committee_name.lower()]
    
    # Aggregate
    spending = df_txn.groupby('Committee_Name', dropna=False)['amount'].agg(['sum', 'count']).reset_index()
    spending.columns = ['committee', 'total_spent', 'transaction_count']
    spending = spending.sort_values('total_spent', ascending=False)
    
    return json.dumps({
        'semester': semester if semester else 'all time',
        'committee_filter': committee_name if committee_name else 'all committees',
        'spending': spending.to_dict('records')
    }, default=str)


def get_available_semesters() -> str:
    """Get list of all available semesters with their date ranges."""
    df_terms = DATA['terms']
    result = df_terms[['Semester', 'start_date', 'end_date']].copy()
    result['start_date'] = result['start_date'].dt.strftime('%Y-%m-%d')
    result['end_date'] = result['end_date'].dt.strftime('%Y-%m-%d')
    
    return json.dumps({
        'semesters': result.to_dict('records')
    }, default=str)


def get_available_committees() -> str:
    """Get list of all committees."""
    df_committees = DATA['committees']
    return json.dumps({
        'committees': df_committees[['CommitteeID', 'Committee_Name', 'Committee_Type']].to_dict('records')
    })


# ============================================================================
# GEMINI FUNCTION CALLING SETUP
# ============================================================================

# Define function declarations for Gemini
tools = [
    {
        "function_declarations": [
            {
                "name": "filter_transactions_by_amount",
                "description": "Filter transactions by amount range. Use this when asked about transactions over/under a specific dollar amount.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_amount": {
                            "type": "number",
                            "description": "Minimum absolute amount in dollars (e.g., 500 for $500+)"
                        },
                        "max_amount": {
                            "type": "number",
                            "description": "Maximum absolute amount in dollars"
                        },
                        "transaction_type": {
                            "type": "string",
                            "enum": ["income", "expense"],
                            "description": "Filter by income or expense transactions"
                        }
                    }
                }
            },
            {
                "name": "filter_transactions_by_semester",
                "description": "Filter transactions by semester. Use this when asked about a specific semester like 'Fall 2024' or 'Spring 2025'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "semester": {
                            "type": "string",
                            "description": "Semester name like 'Fall 2024', 'Spring 2025', etc."
                        },
                        "transaction_type": {
                            "type": "string",
                            "enum": ["income", "expense"],
                            "description": "Filter by income or expense"
                        }
                    },
                    "required": ["semester"]
                }
            },
            {
                "name": "filter_transactions_by_account",
                "description": "Filter transactions by payment account (Venmo or Wells Fargo).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_type": {
                            "type": "string",
                            "description": "Account type: 'venmo' or 'wells'"
                        },
                        "semester": {
                            "type": "string",
                            "description": "Optional semester filter"
                        }
                    },
                    "required": ["account_type"]
                }
            },
            {
                "name": "get_committee_spending",
                "description": "Get spending breakdown by committee.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "committee_name": {
                            "type": "string",
                            "description": "Specific committee name (optional)"
                        },
                        "semester": {
                            "type": "string",
                            "description": "Filter by semester (optional)"
                        }
                    }
                }
            },
            {
                "name": "get_available_semesters",
                "description": "Get list of all available semesters with date ranges.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_available_committees",
                "description": "Get list of all committees.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    }
]

# Function mapping
FUNCTION_MAP = {
    "filter_transactions_by_amount": filter_transactions_by_amount,
    "filter_transactions_by_semester": filter_transactions_by_semester,
    "filter_transactions_by_account": filter_transactions_by_account,
    "get_committee_spending": get_committee_spending,
    "get_available_semesters": get_available_semesters,
    "get_available_committees": get_available_committees
}


# ============================================================================
# CHAT INTERFACE
# ============================================================================

# Initialize Gemini
try:
    genai.configure(api_key=st.secrets["google"]["api_key"])
    model = genai.GenerativeModel(
        'gemini-2.0-flash',
        tools=tools
    )
except Exception as e:
    st.error(f"Failed to initialize AI: {e}")
    st.stop()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Example questions
st.markdown("### 💡 Try These Questions")
examples = [
    "Show all transactions over $500",
    "What's the total Venmo income in Fall 2025?",
    "Which committee spent the most in Spring 2025?",
    "List all available semesters"
]

cols = st.columns(2)
for idx, example in enumerate(examples):
    with cols[idx % 2]:
        if st.button(example, key=f"ex_{idx}", use_container_width=True):
            st.session_state.user_input = example

st.markdown("---")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("Ask about AIS finances...") or st.session_state.pop("user_input", None)

if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get AI response with function calling
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                # Start chat
                chat = model.start_chat()
                response = chat.send_message(user_input)
                
                # Handle function calls
                while response.candidates[0].content.parts[0].function_call:
                    function_call = response.candidates[0].content.parts[0].function_call
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    
                    # Execute the function
                    if function_name in FUNCTION_MAP:
                        function_result = FUNCTION_MAP[function_name](**function_args)
                        
                        # Send result back to model
                        response = chat.send_message(
                            genai.protos.Content(
                                parts=[genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=function_name,
                                        response={"result": function_result}
                                    )
                                )]
                            )
                        )
                
                # Get final text response
                answer = response.text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Clear chat button
if st.button("🗑️ Clear Chat"):
    st.session_state.messages = []
    st.rerun()
