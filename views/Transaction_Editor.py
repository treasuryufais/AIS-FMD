import streamlit as st
import pandas as pd
import time
from utils import load_committees_df, load_transactions_df, load_terms_df, get_admin
from components import animated_typing_title, apply_nav_title

# Initialize UI
apply_nav_title()
animated_typing_title("Transaction Editor")

st.markdown("""
### 🎯 How to Edit Transactions

Welcome to the Transaction Editor! This tool makes it easy to manage and update transaction details. Here's how it works: """)

col = [st.columns(4)]
with col[0][0]:
    st.markdown("""
    **Step 1: Select a Month**
    - 📅 Use the month selector to find the transactions you want to edit
    - All transactions for the selected month will be displayed in a table below
    """)
with col[0][1]:
    st.markdown("""
    **Step 2: Make Your Changes**
    - 🔄 Update transaction details using the dropdown menus
    - 📝 Modify committee assignments and purposes as needed
    - ✨ Changes are highlighted in real-time for easy tracking
    """)
with col[0][2]:
    st.markdown("""
    **Step 3: Save Your Updates**
    - ✅ Review your changes in the preview table
    - 💾 Click "Save Changes" to update the database
    - 🔒 All changes are validated before saving
    """)
with col[0][3]:
    st.markdown("""
    **Pro Tips:**
    - Filter by committee to focus on specific transactions
    - Use the search bar to find specific entries
    - Green highlights show which fields you've modified
    """)

st.divider()

# Load data
@st.cache_data
def load_editor_data():
    df_committees = load_committees_df()
    df_transactions = load_transactions_df()
    df_terms = load_terms_df()
    
    # Parse dates
    df_terms["start_date"] = pd.to_datetime(df_terms["start_date"], errors="coerce")
    df_terms["end_date"] = pd.to_datetime(df_terms["end_date"], errors="coerce")
    df_transactions["transaction_date"] = pd.to_datetime(df_transactions["transaction_date"], errors="coerce")
    
    return df_committees, df_transactions, df_terms

df_committees, df_transactions, df_terms = load_editor_data()

# Helper function to map dates to semesters
def get_semester(dt: pd.Timestamp) -> str | None:
    if pd.isna(dt):
        return None
    mask = (df_terms["start_date"] <= dt) & (df_terms["end_date"] >= dt)
    semesters = df_terms.loc[mask, "Semester"]
    return semesters.iloc[0] if not semesters.empty else None

# Initialize data and filters
available_semesters = (
    df_terms[["Semester", "start_date"]]
    .dropna()
    .sort_values("start_date")
    ["Semester"]
    .tolist()
)

selected_semester = st.selectbox(
    "Select Semester",
    available_semesters,
    index=len(available_semesters) - 1 if available_semesters else 0
)

# Filter transactions based on semester
filtered_transactions = df_transactions.copy()
filtered_transactions["Semester"] = filtered_transactions["transaction_date"].apply(get_semester)
filtered_transactions = filtered_transactions[filtered_transactions["Semester"] == selected_semester]

# Month selection
months = sorted(filtered_transactions["transaction_date"].dt.to_period('M').unique())
if not months:
    st.info("No transactions found for the selected semester.")
    st.stop()

# Clear month selector when semester changes
if "last_semester" not in st.session_state or st.session_state.last_semester != selected_semester:
    st.session_state.last_semester = selected_semester
    if "transaction_month_selector" in st.session_state:
        del st.session_state.transaction_month_selector

# Add "All Months" option to the beginning of the list
month_options = ["All Months"] + months

# Initialize default month index (0 = All Months)
default_month_index = 0

# Month selector - let the widget manage its own state
selected_month_option = st.selectbox(
    "Select Month to Edit",
    month_options,
    format_func=lambda x: "All Months in Semester" if x == "All Months" else x.strftime("%B %Y"),
    key="transaction_month_selector",
    index=default_month_index
)

# Get transactions for selected month or all months
if selected_month_option == "All Months":
    month_transactions = (
        filtered_transactions
        .merge(df_committees[["CommitteeID", "Committee_Name"]], 
               left_on="budget_category", right_on="CommitteeID", how="left")
        .sort_values("transaction_date")
    )
else:
    month_transactions = (
        filtered_transactions[filtered_transactions["transaction_date"].dt.to_period('M') == selected_month_option]
        .merge(df_committees[["CommitteeID", "Committee_Name"]], 
               left_on="budget_category", right_on="CommitteeID", how="left")
        .sort_values("transaction_date")
    )

# Add filters side by side
col1, col2, col3 = st.columns(3)

with col1:
    # Account/Category filter
    account_filter = st.selectbox(
        "Filter by Category",
        ["All", "Uncategorized", "Wells Fargo", "Venmo"],
        index=0,
        key="transaction_account_filter"
    )

with col2:
    # Search filter for details column
    search_term = st.text_input(
        "Search Details",
        placeholder="Enter keywords...",
        key="transaction_search_filter",
        help="Search for specific words in transaction details"
    )

with col3:
    # Type filter: All / Income / Expense
    type_filter = st.selectbox(
        "Filter by Transaction Type",
        ["All", "Income", "Expense"],
        index=0,
        key="transaction_type_filter"
    )

# Apply account filter
if account_filter == "Uncategorized":
    month_transactions = month_transactions[
        month_transactions["budget_category"].isna() | 
        (month_transactions["budget_category"] == "") |
        month_transactions["purpose"].isna() | 
        (month_transactions["purpose"] == "")
    ]
elif account_filter == "Wells Fargo":
    month_transactions = month_transactions[
        month_transactions["account"].str.lower().str.contains("well", na=False)
    ]
elif account_filter == "Venmo":
    month_transactions = month_transactions[
        month_transactions["account"].str.lower().str.contains("venmo", na=False)
    ]

# Apply search filter with sanitization
if search_term:
    # Sanitize input: remove special regex characters to prevent issues
    import re
    # Escape special regex characters for safe searching
    sanitized_search = re.escape(search_term.strip())
    if sanitized_search:  # Only apply if there's something to search after sanitization
        month_transactions = month_transactions[
            month_transactions["details"].str.contains(sanitized_search, case=False, na=False, regex=True)
        ]

# Apply type filter
if type_filter == "Income":
    month_transactions = month_transactions[month_transactions["amount"] > 0]
elif type_filter == "Expense":
    month_transactions = month_transactions[month_transactions["amount"] < 0]

if not month_transactions.empty:
    # Create purpose options
    purpose_options = [
        "Dues", "Food & Drink", "Tax", "Road Trip", "Social Events",
        "Sponsorship / Donation", "Travel Reimbursement", "Transfers",
        "Merch", "Professional Events", "Misc.", "ISOM Passport",
        "GBM Catering", "Formal", "Refunded", "Meeting Food",
        "Technology", "Marketing", "Professional Development"
    ]
    purpose_options.sort()
    
    # Create committee mapping for display
    committee_mapping = {str(i): name for i, name in 
                        df_committees[["CommitteeID", "Committee_Name"]].values}
    # Create committee options with ID and name combined
    committee_options = [""] + [f"{i} - {committee_mapping.get(str(i), '')}" for i in range(1, 19)]
    
    # Initialize or refresh edited data when semester, month, or filter changes
    current_filter_key = f"{selected_semester}-{selected_month_option}-{account_filter}-{search_term}-{type_filter}"
    if "edited_data" not in st.session_state or st.session_state.get("edited_filter_key") != current_filter_key:
        st.session_state.edited_data = month_transactions.copy()
        # Convert budget_category to the combined format for display
        st.session_state.edited_data['budget_category'] = st.session_state.edited_data['budget_category'].apply(
            lambda x: f"{int(x)} - {committee_mapping.get(str(int(x)), '')}" if pd.notna(x) else ""
        )
        st.session_state.edited_filter_key = current_filter_key
    
    with st.form("transaction_editor"):
        # Create an editable dataframe
        edited_df = st.session_state.edited_data.copy()
        
        # Convert data for display (keep transaction_date as datetime for DateColumn)
        display_df = edited_df.copy()
        display_df["amount"] = display_df["amount"].apply(lambda x: f"${x:,.2f}")
        
        # Create editors for purpose, budget, and date columns
        editors = {
            "transaction_date": st.column_config.DateColumn(
                "Date",
                format="YYYY-MM-DD",
                required=True,
                help="Select the transaction date",
            ),
            "purpose": st.column_config.SelectboxColumn(
                "Purpose",
                options=purpose_options,  # Removed empty option to prevent accidental clearing
                required=False,
                default=None
            ),
            "budget_category": st.column_config.SelectboxColumn(
                "Committee",
                options=committee_options,
                required=False,
                default=None,
                help="Select the committee ID. Leave empty to clear the committee.",
            )
        }
        
        # Display editable dataframe
        edited_df = st.data_editor(
            display_df[["transaction_date", "amount", "details", "purpose", "budget_category", "account"]],
            column_config={
                "amount": st.column_config.TextColumn(
                    "Amount",
                    disabled=True,
                ),
                "details": st.column_config.TextColumn(
                    "Details",
                    disabled=True,
                ),
                "account": st.column_config.TextColumn(
                    "Account",
                    disabled=True,
                ),
                **editors
            },
            disabled=False,
            hide_index=True,
            key="transaction_editor"
        )
        
        submitted = st.form_submit_button("💾 Save Changes")
        
        if submitted:
            try:
                admin = get_admin()
                successful_updates = []
                failed_updates = []
                
                for idx, row in edited_df.iterrows():
                    original = st.session_state.edited_data.loc[idx]
                    
                    # Convert budget_category to int if not empty
                    budget_cat = row["budget_category"]
                    
                    if pd.notna(budget_cat) and budget_cat != "":  # Check if value is present
                        if isinstance(budget_cat, str):
                            try:
                                budget_cat = int(budget_cat.split(" - ")[0])
                            except (ValueError, IndexError):
                                budget_cat = None
                        elif isinstance(budget_cat, (int, float)):
                            budget_cat = int(budget_cat)
                        else:
                            budget_cat = None
                    else:
                        budget_cat = None
                    
                    # Convert date to proper format
                    transaction_date = pd.to_datetime(row["transaction_date"]).strftime("%Y-%m-%d") if pd.notna(row["transaction_date"]) else None
                    
                    # Compare changes carefully
                    current_purpose = row["purpose"] if pd.notna(row["purpose"]) and row["purpose"] != "" else None
                    current_budget = budget_cat
                    current_date = transaction_date
                    
                    original_purpose = original["purpose"] if pd.notna(original["purpose"]) else None
                    original_budget = original["budget_category"] if pd.notna(original["budget_category"]) else None
                    original_date = pd.to_datetime(original["transaction_date"]).strftime("%Y-%m-%d") if pd.notna(original["transaction_date"]) else None
                    
                    # Check if values actually changed
                    purpose_changed = current_purpose != original_purpose
                    budget_changed = current_budget != original_budget
                    date_changed = current_date != original_date
                    
                    if purpose_changed or budget_changed or date_changed:
                        try:
                            update_data = {
                                "purpose": current_purpose,
                                "budget_category": current_budget,
                                "transaction_date": current_date
                            }
                            
                            response = admin.table("transactions").update(update_data).eq(
                                "transactionid", original["transactionid"]
                            ).execute()
                            
                            if response.data:
                                successful_updates.append(original["transactionid"])
                            else:
                                failed_updates.append(original["transactionid"])
                                
                        except Exception as e:
                            failed_updates.append(original["transactionid"])
                
                # Show simple status message and refresh
                if successful_updates and not failed_updates:
                    st.success(f"✅ Successfully updated {len(successful_updates)} transactions!")
                    # Clear caches and force refresh
                    st.cache_data.clear()
                    if "edited_data" in st.session_state:
                        del st.session_state.edited_data
                    time.sleep(1)  # Brief pause to ensure message is seen
                    st.rerun()
                elif failed_updates:
                    st.error(f"❌ Failed to update {len(failed_updates)} transactions. Please try again.")
                elif not successful_updates and not failed_updates:
                    st.info("No changes were made.")
                    
            except Exception as e:
                st.error(f"Error updating transactions: {str(e)}")
else:
    st.info("No transactions found for the selected month.")