import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from utils import load_committees_df, load_committee_budgets_df, load_transactions_df, load_terms_df, get_supabase, get_admin
from components import animated_typing_title, apply_nav_title

# Initialize UI
apply_nav_title()
animated_typing_title("UF AIS Financial Dashboard")
st.divider()

st.markdown("""
### 📊 UF AIS Financial Dashboard

Get a **clear and engaging view** of UF AIS financial data across all committees and semesters!  

**How to use:**
- 🗂 **Select a semester & committee** from the sidebar filters  
- 💰 Analyze **spending patterns**, **budget utilization**, and **financial trends**  
- 📈 See how **metrics change** compared to the previous semester  
- ⏳ Track financial performance **over time** with ease  
""")

st.divider()

# Load data
@st.cache_data
def load_data():
    df_committees = load_committees_df()
    df_budgets = load_committee_budgets_df()
    df_transactions = load_transactions_df()
    df_terms = load_terms_df()
    
    # Parse dates
    df_terms["start_date"] = pd.to_datetime(df_terms["start_date"], errors="coerce")
    df_terms["end_date"] = pd.to_datetime(df_terms["end_date"], errors="coerce")
    df_transactions["transaction_date"] = pd.to_datetime(df_transactions["transaction_date"], errors="coerce")
    
    return df_committees, df_budgets, df_transactions, df_terms

df_committees, df_budgets, df_transactions, df_terms = load_data()

# Helper function to map dates to semesters
def get_semester(dt: pd.Timestamp) -> str | None:
    if pd.isna(dt):
        return None
    mask = (df_terms["start_date"] <= dt) & (df_terms["end_date"] >= dt)
    semesters = df_terms.loc[mask, "Semester"]
    return semesters.iloc[0] if not semesters.empty else None

# Sidebar filters
st.sidebar.header("📊 Dashboard Filters")

# Semester filter - sort chronologically by start date
available_semesters = (
    df_terms[["Semester", "start_date"]]
    .dropna()
    .sort_values("start_date")
    ["Semester"]
    .tolist()
)
selected_semester = st.sidebar.selectbox(
    "Select Semester",
    available_semesters,
    index=len(available_semesters) - 1 if available_semesters else 0
)

# Committee filter
committee_options = ["All Committees"] + sorted(df_committees[df_committees["Committee_Type"] == "committee"]["Committee_Name"].tolist())
selected_committee = st.sidebar.selectbox("Select Committee", committee_options)

# Main dashboard content
st.header("💰 Financial Overview")

# Key metrics row
col1, col2, col3, col4 = st.columns(4)

# Helper function to get previous semester
def get_previous_semester(current_semester):
    """Get the previous semester from the list of available semesters"""
    if current_semester in available_semesters:
        current_index = available_semesters.index(current_semester)
        if current_index > 0:
            return available_semesters[current_index - 1]
    return None

# Helper function to get next semester (for debugging)
def get_next_semester(current_semester):
    """Get the next semester from the list of available semesters"""
    if current_semester in available_semesters:
        current_index = available_semesters.index(current_semester)
        if current_index < len(available_semesters) - 1:
            return available_semesters[current_index + 1]
    return None

# Filter transactions based on selections
filtered_transactions = df_transactions.copy()
filtered_transactions["Semester"] = filtered_transactions["transaction_date"].apply(get_semester)
filtered_transactions = filtered_transactions[filtered_transactions["Semester"] == selected_semester]

# Get previous semester data for comparison
previous_semester = get_previous_semester(selected_semester)
if previous_semester:
    previous_transactions = df_transactions.copy()
    previous_transactions["Semester"] = previous_transactions["transaction_date"].apply(get_semester)
    previous_transactions = previous_transactions[previous_transactions["Semester"] == previous_semester]
else:
    previous_transactions = pd.DataFrame(columns=filtered_transactions.columns)

# Calculate metrics for current semester
total_income = filtered_transactions[filtered_transactions["amount"] > 0]["amount"].sum()
total_expenses = abs(filtered_transactions[filtered_transactions["amount"] < 0]["amount"].sum())
net_income = total_income - total_expenses
total_transactions = len(filtered_transactions)

# Calculate metrics for previous semester
prev_total_income = previous_transactions[previous_transactions["amount"] > 0]["amount"].sum()
prev_total_expenses = abs(previous_transactions[previous_transactions["amount"] < 0]["amount"].sum())
prev_net_income = prev_total_income - prev_total_expenses
prev_total_transactions = len(previous_transactions)

# Calculate deltas (current - previous)
income_delta = round(total_income - prev_total_income, 2)
expenses_delta = round(total_expenses - prev_total_expenses, 2)
net_income_delta = round(net_income - prev_net_income, 2)
transactions_delta = total_transactions - prev_total_transactions

# Debug information (can be removed later)
if st.sidebar.checkbox("Show Debug Info"):
    st.sidebar.write(f"**Current Semester:** {selected_semester}")
    st.sidebar.write(f"**Previous Semester:** {previous_semester}")
    st.sidebar.write(f"**Current Income:** ${total_income:,.2f}")
    st.sidebar.write(f"**Previous Income:** ${prev_total_income:,.2f}")
    st.sidebar.write(f"**Income Delta:** ${income_delta:,.2f}")
    st.sidebar.write(f"**Available Semesters:** {available_semesters}")

with col1:
    st.metric(
        label="Total Income",
        value=f"${total_income:,.2f}",
        delta=income_delta,
        delta_color="normal"
    )

with col2:
    st.metric(
        label="Total Expenses",
        value=f"${total_expenses:,.2f}",
        delta=expenses_delta,
        delta_color="normal"
    )

with col3:
    st.metric(
        label="Net Income",
        value=f"${net_income:,.2f}",
        delta=net_income_delta,
        delta_color="normal"
    )

with col4:
    st.metric(
        label="Total Transactions",
        value=f"{total_transactions:,}",
        delta=transactions_delta,
        delta_color="normal"
    )

st.divider()

# Budget vs Spending Analysis
st.header("📈 Budget vs Spending Analysis")

# Prepare budget data
df_budgets_clean = (
    df_budgets
    .merge(df_terms[["TermID", "Semester"]], left_on="termid", right_on="TermID", how="left")
    .merge(df_committees[["CommitteeID", "Committee_Name", "Committee_Type"]], 
           left_on="committeeid", right_on="CommitteeID", how="left")
    .query("Committee_Type == 'committee'")
    .loc[:, ["Semester", "committeebudgetid", "budget_amount", "Committee_Name"]]
)

# Prepare spending data
df_spending = (
    filtered_transactions
    .merge(df_committees[["CommitteeID", "Committee_Name", "Committee_Type"]], 
           left_on="budget_category", right_on="CommitteeID", how="left")
    .query("Committee_Type == 'committee' and amount < 0")
    .assign(amount=lambda d: d["amount"].abs())
    .groupby("Committee_Name", as_index=False)["amount"].sum()
    .rename(columns={"amount": "Spent"})
)

# Combine budget and spending
summary = (
    df_budgets_clean.query("Semester == @selected_semester")
    .merge(df_spending, on="Committee_Name", how="left")
    .fillna({"Spent": 0})
    .assign(**{"% Spent": lambda d: d["Spent"] / d["budget_amount"] * 100})
)

# Filter by selected committee if not "All"
if selected_committee != "All Committees":
    summary = summary[summary["Committee_Name"] == selected_committee]

summary["% Spent"].fillna(0, inplace=True)
df_display = summary.rename(columns={"budget_amount": "Budget"})[["Committee_Name", "Budget", "Spent", "% Spent"]]

# Add historical budget vs spending data
def get_historical_budget_spending():
    # Get all transactions with committee info
    historical_spending = (
        df_transactions
        .merge(df_committees[["CommitteeID", "Committee_Name", "Committee_Type"]], 
               left_on="budget_category", right_on="CommitteeID", how="left")
        .query("Committee_Type == 'committee' and amount < 0")
        .assign(
            amount=lambda d: d["amount"].abs(),
            Semester=lambda d: d["transaction_date"].apply(get_semester)
        )
        .groupby(["Semester", "Committee_Name"], as_index=False)
        ["amount"].sum()
        .rename(columns={"amount": "Spent"})
    )
    
    # Get all budgets
    historical_budget = (
        df_budgets
        .merge(df_terms[["TermID", "Semester"]], left_on="termid", right_on="TermID", how="left")
        .merge(df_committees[["CommitteeID", "Committee_Name", "Committee_Type"]], 
               left_on="committeeid", right_on="CommitteeID", how="left")
        .query("Committee_Type == 'committee'" or "Committee_Name == 'Meeting Food'")
        .loc[:, ["Semester", "Committee_Name", "budget_amount"]]
    )
    
    # Combine budget and spending
    historical_data = (
        historical_budget
        .merge(historical_spending, on=["Semester", "Committee_Name"], how="outer")
        .fillna({"Spent": 0, "budget_amount": 0})
    )
    
    # Sort chronologically by merging with terms to get start_date
    historical_data = (
        historical_data
        .merge(df_terms[["Semester", "start_date"]], on="Semester", how="left")
        .sort_values("start_date")
        .drop(columns=["start_date"])
    )
    
    return historical_data

# Display table and chart
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Budget Summary")
    st.dataframe(
        df_display.sort_values("% Spent", ascending=False)
        .style.format({"Budget": "${:,.2f}", "Spent": "${:,.2f}", "% Spent": "{:.1f}%"}),
        use_container_width=True,
        hide_index=True
    )
    
    

with col2:
    if not df_display.empty:
        # Sort data for display
        sorted_data = df_display.sort_values("% Spent", ascending=True)
        
        fig = px.bar(
            sorted_data,
            x="% Spent",
            y="Committee_Name",
            orientation="h",
            text=sorted_data["% Spent"].round(1).astype(str) + "%",
            labels={"% Spent": "% of Budget Spent", "Committee_Name": "Committee"},
            color="% Spent",
            color_continuous_scale="Blues",
            custom_data=["Committee_Name", "% Spent", "Spent", "Budget"]
        )
        
        fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>" +
                         "Percent Spent: %{customdata[1]:.1f}%<br>" +
                         "Spent: $%{customdata[2]:,.2f}<br>" +
                         "Budget: $%{customdata[3]:,.2f}<extra></extra>",
            showlegend=False
        )
        
        max_val = max(100, sorted_data["% Spent"].max() * 1.1)
        fig.update_layout(
            xaxis=dict(range=[0, max_val]),
            margin=dict(l=150, r=20, t=20, b=20),
            height=400,
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No budget data available for the selected filters.")

st.divider()

# Financial Trends Analysis
st.header("📈 Financial Trends")

# Get historical data
historical_data = get_historical_budget_spending()

if not historical_data.empty:
    if selected_committee != "All Committees":
        # Filter for specific committee
        historical_data = historical_data[historical_data["Committee_Name"] == selected_committee]
        
        # Create two-part visualization for specific committee
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=(
                f"{selected_committee} - Budget vs Actual Spending",
                "Spending Efficiency (% of Budget Used)"
            ),
            vertical_spacing=0.15
        )
    else:
        # Aggregate data for all committees
        # First merge with terms to preserve chronological order
        historical_with_dates = historical_data.merge(
            df_terms[["Semester", "start_date"]], 
            on="Semester", 
            how="left"
        )
        
        historical_data = (
            historical_with_dates
            .groupby(["Semester", "start_date"], as_index=False)
            .agg({
                "budget_amount": "sum",
                "Spent": "sum"
            })
            .sort_values("start_date")
            .drop(columns=["start_date"])
        )
        
        # Create single plot for all committees
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=(f"Overall Budget vs Actual Spending",)
        )
    
    # Add budget vs actual spending bars
    fig.add_trace(
        go.Bar(
            name="Budget",
            x=historical_data["Semester"],
            y=historical_data["budget_amount"],
            marker_color='rgb(53, 138, 255)',  # Bright blue
            hovertemplate="Budget: $%{y:,.2f}<extra></extra>"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            name="Actual Spending",
            x=historical_data["Semester"],
            y=historical_data["Spent"],
            marker_color='rgb(255, 140, 0)',  # Orange
            hovertemplate="Spent: $%{y:,.2f}<extra></extra>"
        ),
        row=1, col=1
    )
    
    if selected_committee != "All Committees":
        # Calculate and add spending efficiency line for specific committee
        historical_data['Efficiency'] = (historical_data['Spent'] / historical_data['budget_amount'] * 100).round(1)
        
        # Add efficiency scatter plot with text labels
        fig.add_trace(
            go.Scatter(
                name="Spending Efficiency",
                x=historical_data["Semester"],
                y=historical_data["Efficiency"],
                mode='lines+markers+text',  # Added text mode
                line=dict(color='rgb(242,142,43)', width=3),
                marker=dict(size=8),
                text=[f"{x:.1f}%" for x in historical_data["Efficiency"]],  # Add percentage labels
                textposition="top center",  # Position labels above points
                textfont=dict(size=10),  # Adjust text size
                hovertemplate="Efficiency: %{y:.1f}%<extra></extra>"
            ),
            row=2, col=1
        )
        
        # Add target efficiency reference line
        fig.add_trace(
            go.Scatter(
                name="Target Efficiency",
                x=historical_data["Semester"],
                y=[100] * len(historical_data["Semester"]),
                mode='lines',
                line=dict(color='rgba(169,169,169,0.5)', dash='dash'),
                hoverinfo='skip'
            ),
            row=2, col=1
        )
        
        # Update y-axes for both plots
        fig.update_yaxes(title_text="Amount ($)", row=1, col=1)
        fig.update_yaxes(title_text="% of Budget Used", row=2, col=1, 
                        range=[0, max(120, historical_data["Efficiency"].max() * 1.1)])
        
        # Set height for two-plot layout
        height = 700
    else:
        # Update y-axis for single plot
        fig.update_yaxes(title_text="Amount ($)", row=1, col=1)
        # Set height for single-plot layout
        height = 400
    
    # Update layout
    fig.update_layout(
        height=height,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        barmode='group'
    )
    
    # Add budget vs spending annotations with increased spacing
    for i, row in historical_data.iterrows():
        if pd.notna(row['budget_amount']) and pd.notna(row['Spent']):
            fig.add_annotation(
                x=row['Semester'],
                y=max(row['budget_amount'], row['Spent']),
                text=f"${abs(row['budget_amount'] - row['Spent']):,.0f}<br>{'under' if row['budget_amount'] > row['Spent'] else 'over'}",
                yshift=25,  # Increased spacing from bars
                showarrow=False,
                font=dict(size=10),
                row=1, col=1
            )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add insights for specific committee
    if selected_committee != "All Committees" and len(historical_data) > 1:
        latest_efficiency = historical_data.iloc[-1]["Efficiency"]
        avg_efficiency = historical_data["Efficiency"].mean()
        efficiency_trend = "increasing" if historical_data.iloc[-1]["Efficiency"] > historical_data.iloc[-2]["Efficiency"] else "decreasing"
        
        st.info(f"""
        📊 **Financial Insights:**
        - Latest spending efficiency: **{latest_efficiency:.1f}%** of budget used
        - Average efficiency across periods: **{avg_efficiency:.1f}%**
        - Spending efficiency is **{efficiency_trend}** compared to last semester
        """)
else:
    st.info("No historical data available for the selected filters.")

st.divider()

# Income and Expense Breakdown
st.header("💸 Income & Expense Breakdown")

# Apply committee filter to income and expense data
if selected_committee != "All Committees":
    committee_id = df_committees[df_committees["Committee_Name"] == selected_committee]["CommitteeID"].iloc[0]
    filtered_transactions_for_categories = filtered_transactions[filtered_transactions["budget_category"] == committee_id]
else:
    filtered_transactions_for_categories = filtered_transactions

# Income analysis
income_data = filtered_transactions_for_categories[filtered_transactions_for_categories["amount"] > 0].copy()
income_data["Income_Type"] = "Other"

# Categorize income
income_categories = {
    "Dues": ["Dues"],
    "Merchandise": ["Merch", "Head Shot"],
    "Sponsorship/Donation": ["Sponsorship", "Donation"],
    "Events": ["Social Events", "Formal", "Professional Events", "Fundraiser", "ISOM Passport"],
    "Refunds": ["Reimbursement", "Refunded"],
    "Transfers": ["Transfers"]
}

for category, keywords in income_categories.items():
    for keyword in keywords:
        income_data.loc[income_data["purpose"].str.contains(keyword, case=False, na=False), "Income_Type"] = category

# Expense analysis
expense_data = filtered_transactions_for_categories[filtered_transactions_for_categories["amount"] < 0].copy()
expense_data["amount"] = expense_data["amount"].abs()
expense_data["Expense_Type"] = "Other"

# Categorize expenses
expense_categories = {
    "Merchandise": ["Merch", "Head Shot"],
    "Events": ["Social Events", "GBM Catering", "Formal", "Professional Events", "Fundraiser", "Road Trip", "ISOM Passport"],
    "Food & Drink": ["Food", "Drink", "Catering"],
    "Travel": ["Travel"],
    "Reimbursements": ["Reimbursement", "Refunded"],
    "Transfers": ["Transfers"],
    "Tax & Fees": ["Tax"],
    "Miscellaneous": ["Misc"]
}

for category, keywords in expense_categories.items():
    for keyword in keywords:
        expense_data.loc[expense_data["purpose"].str.contains(keyword, case=False, na=False), "Expense_Type"] = category

# Display charts
col1, col2 = st.columns(2)

with col1:
    st.subheader("Income by Category")
    if not income_data.empty:
        income_by_type = income_data.groupby("Income_Type", as_index=False)["amount"].sum()
        fig_income = px.pie(
            income_by_type, 
            values="amount", 
            names="Income_Type", 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_income.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Amount: $%{value:,.2f}<br>Percent: %{percent}<extra></extra>"
        )
        fig_income.update_layout(margin=dict(t=20, b=20), height=400)
        st.plotly_chart(fig_income, use_container_width=True)
    else:
        st.info("No income data available for the selected period.")

with col2:
    st.subheader("Expenses by Category")
    if not expense_data.empty:
        expense_by_type = expense_data.groupby("Expense_Type", as_index=False)["amount"].sum()
        fig_expense = px.pie(
            expense_by_type, 
            values="amount", 
            names="Expense_Type", 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set1
        )
        fig_expense.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Amount: $%{value:,.2f}<br>Percent: %{percent}<extra></extra>"
        )
        fig_expense.update_layout(margin=dict(t=20, b=20), height=400)
        st.plotly_chart(fig_expense, use_container_width=True)
    else:
        st.info("No expense data available for the selected period.")
