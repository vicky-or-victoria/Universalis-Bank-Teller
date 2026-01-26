import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing import Optional

class LoanSystem(commands.Cog):
    """Personal and company loan system with interest"""
    
    def __init__(self, bot):
        self.bot = bot
        # Loan configuration
        self.personal_interest_rate = 0.10  # 10% interest
        self.company_interest_rate = 0.08   # 8% interest
        self.max_personal_loan = 100000     # Max $100k personal loan
        self.max_company_loan = 500000      # Max $500k company loan
        self.loan_duration_days = 30        # 30 days to repay
        self.late_fee_rate = 0.05           # 5% late fee per day overdue
        self.max_late_fee_multiplier = 2.0  # Late fees can't exceed 200% of original loan
        
        # Start background task to check for overdue loans
        self.check_overdue_loans.start()
    
    async def get_user_balance(self, user_id: int) -> float:
        """Get user balance"""
        async with self.bot.db.acquire() as conn:
            row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
            if not row:
                await conn.execute("INSERT INTO users (user_id, balance) VALUES ($1, $2)", user_id, 50000)
                return 50000.0
            return float(row['balance'])
    
    async def update_user_balance(self, user_id: int, amount: float):
        """Update user balance"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, user_id
            )
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.check_overdue_loans.cancel()
    
    @tasks.loop(hours=6)
    async def check_overdue_loans(self):
        """Check for overdue loans every 6 hours and apply penalties"""
        try:
            current_time = datetime.now()
            
            async with self.bot.db.acquire() as conn:
                # Check overdue personal loans
                overdue_personal = await conn.fetch(
                    """SELECT id, user_id, principal, interest_amount, total_amount, due_date, late_fees
                       FROM personal_loans 
                       WHERE repaid = FALSE AND due_date < $1""",
                    current_time
                )
                
                for loan in overdue_personal:
                    loan_id = loan['id']
                    user_id = loan['user_id']
                    principal = float(loan['principal'])
                    current_total = float(loan['total_amount'])
                    due_date = loan['due_date']
                    existing_late_fees = float(loan['late_fees']) if loan['late_fees'] else 0
                    
                    # Calculate days overdue
                    days_overdue = (current_time - due_date).days
                    
                    if days_overdue > 0:
                        # Calculate daily late fee
                        daily_late_fee = principal * self.late_fee_rate
                        new_late_fees = daily_late_fee * days_overdue
                        
                        # Cap late fees at max multiplier
                        max_late_fees = principal * self.max_late_fee_multiplier
                        new_late_fees = min(new_late_fees, max_late_fees)
                        
                        # Only update if late fees have increased
                        if new_late_fees > existing_late_fees:
                            new_total = principal + float(loan['interest_amount']) + new_late_fees
                            
                            await conn.execute(
                                "UPDATE personal_loans SET late_fees = $1, total_amount = $2 WHERE id = $3",
                                new_late_fees, new_total, loan_id
                            )
                            
                            print(f"[LOANS] Applied ${new_late_fees - existing_late_fees:.2f} late fees to user {user_id} (Personal Loan #{loan_id})")
                
                # Check overdue company loans
                overdue_company = await conn.fetch(
                    """SELECT cl.id, cl.company_id, c.owner_id, c.name, cl.principal, cl.interest_amount, 
                              cl.total_amount, cl.due_date, cl.late_fees
                       FROM company_loans cl
                       JOIN companies c ON cl.company_id = c.id
                       WHERE cl.repaid = FALSE AND cl.due_date < $1""",
                    current_time
                )
                
                for loan in overdue_company:
                    loan_id = loan['id']
                    company_id = loan['company_id']
                    company_name = loan['name']
                    principal = float(loan['principal'])
                    current_total = float(loan['total_amount'])
                    due_date = loan['due_date']
                    existing_late_fees = float(loan['late_fees']) if loan['late_fees'] else 0
                    
                    # Calculate days overdue
                    days_overdue = (current_time - due_date).days
                    
                    if days_overdue > 0:
                        # Calculate daily late fee
                        daily_late_fee = principal * self.late_fee_rate
                        new_late_fees = daily_late_fee * days_overdue
                        
                        # Cap late fees
                        max_late_fees = principal * self.max_late_fee_multiplier
                        new_late_fees = min(new_late_fees, max_late_fees)
                        
                        # Only update if late fees have increased
                        if new_late_fees > existing_late_fees:
                            new_total = principal + float(loan['interest_amount']) + new_late_fees
                            
                            await conn.execute(
                                "UPDATE company_loans SET late_fees = $1, total_amount = $2 WHERE id = $3",
                                new_late_fees, new_total, loan_id
                            )
                            
                            print(f"[LOANS] Applied ${new_late_fees - existing_late_fees:.2f} late fees to {company_name} (Company Loan #{loan_id})")
            
            print(f"[LOANS] Checked overdue loans: {len(overdue_personal)} personal, {len(overdue_company)} company")
        
        except Exception as e:
            print(f"[LOANS ERROR] Failed to check overdue loans: {e}")
    
    @check_overdue_loans.before_loop
    async def before_check_overdue_loans(self):
        """Wait until bot is ready before starting the loop"""
        await self.bot.wait_until_ready()
    
    @commands.hybrid_command(name="request_loan")
    async def request_personal_loan(self, ctx, amount: float):
        """Request a personal loan
        
        Usage: /request-loan 50000
        """
        if amount <= 0:
            await ctx.send("❌ Loan amount must be positive!")
            return
        
        if amount > self.max_personal_loan:
            await ctx.send(f"❌ Maximum personal loan is **${self.max_personal_loan:,.2f}**!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Check for existing personal loan
            existing_loan = await conn.fetchrow(
                "SELECT id, principal, interest_amount, total_amount, due_date, late_fees FROM personal_loans WHERE user_id = $1 AND repaid = FALSE",
                ctx.author.id
            )
            
            if existing_loan:
                principal = float(existing_loan['principal'])
                interest = float(existing_loan['interest_amount'])
                late_fees = float(existing_loan['late_fees']) if existing_loan['late_fees'] else 0
                total_owed = float(existing_loan['total_amount'])
                due_date = existing_loan['due_date']
                
                # Check if overdue
                is_overdue = datetime.now() > due_date
                days_overdue = (datetime.now() - due_date).days if is_overdue else 0
                
                overdue_msg = f"\n⚠️ **OVERDUE by {days_overdue} days!**" if is_overdue else ""
                late_fee_msg = f"\n**Late Fees:** ${late_fees:,.2f}" if late_fees > 0 else ""
                
                await ctx.send(
                    f"❌ You already have an outstanding loan!{overdue_msg}\n"
                    f"**Principal:** ${principal:,.2f}\n"
                    f"**Interest:** ${interest:,.2f}{late_fee_msg}\n"
                    f"**Total Owed:** ${total_owed:,.2f}\n"
                    f"**Due Date:** {due_date.strftime('%Y-%m-%d')}\n"
                    f"Use `/repay-loan {total_owed:.2f}` to repay it."
                )
                return
            
            # Calculate interest and due date
            interest_amount = amount * self.personal_interest_rate
            total_repayment = amount + interest_amount
            due_date = datetime.now() + timedelta(days=self.loan_duration_days)
            
            # Create loan record
            await conn.execute(
                """INSERT INTO personal_loans (user_id, principal, interest_amount, total_amount, due_date, taken_at, late_fees)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                ctx.author.id, amount, interest_amount, total_repayment, due_date, datetime.now(), 0
            )
            
            # Give money to user
            await self.update_user_balance(ctx.author.id, amount)
        
        new_balance = await self.get_user_balance(ctx.author.id)
        
        embed = discord.Embed(
            title="✅ Loan Approved!",
            description="Your personal loan has been approved and deposited to your account.",
            color=discord.Color.green()
        )
        embed.add_field(name="Loan Amount", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="Interest Rate", value=f"{self.personal_interest_rate * 100:.1f}%", inline=True)
        embed.add_field(name="Interest Charged", value=f"${interest_amount:,.2f}", inline=True)
        embed.add_field(name="Total Repayment", value=f"**${total_repayment:,.2f}**", inline=True)
        embed.add_field(name="Due Date", value=due_date.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=True)
        embed.set_footer(text=f"Use /repay-loan {total_repayment:.2f} to repay | /my-loans to view details")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="request_company_loan")
    async def request_company_loan(self, ctx, company_name: str, amount: float):
        """Request a loan for your company
        
        Usage: /request-company-loan "My Company" 200000
        """
        if amount <= 0:
            await ctx.send("❌ Loan amount must be positive!")
            return
        
        if amount > self.max_company_loan:
            await ctx.send(f"❌ Maximum company loan is **${self.max_company_loan:,.2f}**!")
            return
        
        async with self.bot.db.acquire() as conn:
            # Check company ownership
            company = await conn.fetchrow(
                "SELECT id, balance FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ You don't own a company named **{company_name}**!")
                return
            
            company_id = company['id']
            company_balance = float(company['balance'])
            
            # Check for existing company loan
            existing_loan = await conn.fetchrow(
                "SELECT id, principal, interest_amount, total_amount, due_date, late_fees FROM company_loans WHERE company_id = $1 AND repaid = FALSE",
                company_id
            )
            
            if existing_loan:
                principal = float(existing_loan['principal'])
                interest = float(existing_loan['interest_amount'])
                late_fees = float(existing_loan['late_fees']) if existing_loan['late_fees'] else 0
                total_owed = float(existing_loan['total_amount'])
                due_date = existing_loan['due_date']
                
                # Check if overdue
                is_overdue = datetime.now() > due_date
                days_overdue = (datetime.now() - due_date).days if is_overdue else 0
                
                overdue_msg = f"\n⚠️ **OVERDUE by {days_overdue} days!**" if is_overdue else ""
                late_fee_msg = f"\n**Late Fees:** ${late_fees:,.2f}" if late_fees > 0 else ""
                
                await ctx.send(
                    f"❌ **{company_name}** already has an outstanding loan!{overdue_msg}\n"
                    f"**Principal:** ${principal:,.2f}\n"
                    f"**Interest:** ${interest:,.2f}{late_fee_msg}\n"
                    f"**Total Owed:** ${total_owed:,.2f}\n"
                    f"**Due Date:** {due_date.strftime('%Y-%m-%d')}\n"
                    f"Use `/repay-company-loan \"{company_name}\" {total_owed:.2f}` to repay it."
                )
                return
            
            # Calculate interest and due date
            interest_amount = amount * self.company_interest_rate
            total_repayment = amount + interest_amount
            due_date = datetime.now() + timedelta(days=self.loan_duration_days)
            
            # Create loan record
            await conn.execute(
                """INSERT INTO company_loans (company_id, principal, interest_amount, total_amount, due_date, taken_at, late_fees)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                company_id, amount, interest_amount, total_repayment, due_date, datetime.now(), 0
            )
            
            # Add money to company
            new_company_balance = company_balance + amount
            await conn.execute(
                "UPDATE companies SET balance = $1 WHERE id = $2",
                new_company_balance, company_id
            )
        
        embed = discord.Embed(
            title="✅ Company Loan Approved!",
            description=f"The loan for **{company_name}** has been approved and deposited.",
            color=discord.Color.green()
        )
        embed.add_field(name="Loan Amount", value=f"${amount:,.2f}", inline=True)
        embed.add_field(name="Interest Rate", value=f"{self.company_interest_rate * 100:.1f}%", inline=True)
        embed.add_field(name="Interest Charged", value=f"${interest_amount:,.2f}", inline=True)
        embed.add_field(name="Total Repayment", value=f"**${total_repayment:,.2f}**", inline=True)
        embed.add_field(name="Due Date", value=due_date.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Company Balance", value=f"${new_company_balance:,.2f}", inline=True)
        embed.set_footer(text=f"Use /repay-company-loan \"{company_name}\" {total_repayment:.2f} to repay")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="repay_loan")
    async def repay_personal_loan(self, ctx, amount: Optional[float] = None):
        """Repay your personal loan (full or partial)
        
        Usage: 
        - /repay-loan - Repay full amount
        - /repay-loan 25000 - Repay partial amount
        """
        async with self.bot.db.acquire() as conn:
            loan = await conn.fetchrow(
                "SELECT id, principal, interest_amount, total_amount, due_date, late_fees FROM personal_loans WHERE user_id = $1 AND repaid = FALSE",
                ctx.author.id
            )
            
            if not loan:
                await ctx.send("❌ You don't have any outstanding personal loans!")
                return
            
            loan_id = loan['id']
            total_owed = float(loan['total_amount'])
            principal = float(loan['principal'])
            interest = float(loan['interest_amount'])
            late_fees = float(loan['late_fees']) if loan['late_fees'] else 0
            due_date = loan['due_date']
            
            # If no amount specified, repay full amount
            if amount is None:
                amount = total_owed
            
            if amount <= 0:
                await ctx.send("❌ Repayment amount must be positive!")
                return
            
            if amount > total_owed:
                await ctx.send(f"❌ You only owe **${total_owed:,.2f}**! Cannot overpay.")
                return
            
            # Check balance
            balance = await self.get_user_balance(ctx.author.id)
            
            if balance < amount:
                await ctx.send(f"❌ Insufficient funds! Need ${amount:,.2f}, have ${balance:,.2f}")
                return
            
            # Process repayment
            await self.update_user_balance(ctx.author.id, -amount)
            
            remaining_amount = total_owed - amount
            
            if remaining_amount <= 0.01:  # Fully repaid (with small rounding tolerance)
                await conn.execute(
                    "UPDATE personal_loans SET repaid = TRUE, repaid_at = $1 WHERE id = $2",
                    datetime.now(), loan_id
                )
                
                embed = discord.Embed(
                    title="🎉 Loan Fully Repaid!",
                    description="Congratulations! Your personal loan has been fully repaid.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Amount Paid", value=f"${amount:,.2f}", inline=True)
                embed.add_field(name="Principal", value=f"${principal:,.2f}", inline=True)
                embed.add_field(name="Interest", value=f"${interest:,.2f}", inline=True)
                if late_fees > 0:
                    embed.add_field(name="Late Fees Paid", value=f"${late_fees:,.2f}", inline=True)
                if late_fees > 0:
                    embed.add_field(name="Late Fees Paid", value=f"${late_fees:,.2f}", inline=True)
            else:
                # Partial repayment
                await conn.execute(
                    "UPDATE personal_loans SET total_amount = $1 WHERE id = $2",
                    remaining_amount, loan_id
                )
                
                embed = discord.Embed(
                    title="💳 Partial Loan Repayment",
                    description="Your payment has been processed.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Amount Paid", value=f"${amount:,.2f}", inline=True)
                embed.add_field(name="Remaining", value=f"**${remaining_amount:,.2f}**", inline=True)
                embed.add_field(name="Due Date", value=due_date.strftime("%Y-%m-%d"), inline=True)
        
        new_balance = await self.get_user_balance(ctx.author.id)
        embed.add_field(name="New Balance", value=f"${new_balance:,.2f}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="repay_company_loan")
    async def repay_company_loan(self, ctx, company_name: str, amount: Optional[float] = None):
        """Repay your company loan (full or partial)
        
        Usage: 
        - /repay-company-loan "My Company" - Repay full amount
        - /repay-company-loan "My Company" 100000 - Repay partial amount
        """
        async with self.bot.db.acquire() as conn:
            company = await conn.fetchrow(
                "SELECT id, balance FROM companies WHERE owner_id = $1 AND name = $2",
                ctx.author.id, company_name
            )
            
            if not company:
                await ctx.send(f"❌ You don't own a company named **{company_name}**!")
                return
            
            company_id = company['id']
            company_balance = float(company['balance'])
            
            loan = await conn.fetchrow(
                "SELECT id, principal, interest_amount, total_amount, due_date, late_fees FROM company_loans WHERE company_id = $1 AND repaid = FALSE",
                company_id
            )
            
            if not loan:
                await ctx.send(f"❌ **{company_name}** doesn't have any outstanding loans!")
                return
            
            loan_id = loan['id']
            total_owed = float(loan['total_amount'])
            principal = float(loan['principal'])
            interest = float(loan['interest_amount'])
            late_fees = float(loan['late_fees']) if loan['late_fees'] else 0
            due_date = loan['due_date']
            
            # If no amount specified, repay full amount
            if amount is None:
                amount = total_owed
            
            if amount <= 0:
                await ctx.send("❌ Repayment amount must be positive!")
                return
            
            if amount > total_owed:
                await ctx.send(f"❌ Company only owes **${total_owed:,.2f}**! Cannot overpay.")
                return
            
            # Check company balance
            if company_balance < amount:
                await ctx.send(f"❌ **{company_name}** has insufficient funds! Need ${amount:,.2f}, have ${company_balance:,.2f}")
                return
            
            # Process repayment
            new_company_balance = company_balance - amount
            await conn.execute(
                "UPDATE companies SET balance = $1 WHERE id = $2",
                new_company_balance, company_id
            )
            
            remaining_amount = total_owed - amount
            
            if remaining_amount <= 0.01:  # Fully repaid
                await conn.execute(
                    "UPDATE company_loans SET repaid = TRUE, repaid_at = $1 WHERE id = $2",
                    datetime.now(), loan_id
                )
                
                embed = discord.Embed(
                    title="🎉 Company Loan Fully Repaid!",
                    description=f"**{company_name}** has fully repaid its loan!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Amount Paid", value=f"${amount:,.2f}", inline=True)
                embed.add_field(name="Principal", value=f"${principal:,.2f}", inline=True)
                embed.add_field(name="Interest", value=f"${interest:,.2f}", inline=True)
            else:
                # Partial repayment
                await conn.execute(
                    "UPDATE company_loans SET total_amount = $1 WHERE id = $2",
                    remaining_amount, loan_id
                )
                
                embed = discord.Embed(
                    title="💳 Partial Company Loan Repayment",
                    description=f"**{company_name}**'s payment has been processed.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Amount Paid", value=f"${amount:,.2f}", inline=True)
                embed.add_field(name="Remaining", value=f"**${remaining_amount:,.2f}**", inline=True)
                embed.add_field(name="Due Date", value=due_date.strftime("%Y-%m-%d"), inline=True)
            
            embed.add_field(name="Company Balance", value=f"${new_company_balance:,.2f}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="my_loans")
    async def view_my_loans(self, ctx):
        """View all your personal and company loans"""
        async with self.bot.db.acquire() as conn:
            # Get personal loans
            personal_loans = await conn.fetch(
                """SELECT principal, interest_amount, total_amount, due_date, taken_at, repaid, repaid_at, late_fees
                   FROM personal_loans WHERE user_id = $1 ORDER BY taken_at DESC LIMIT 5""",
                ctx.author.id
            )
            
            # Get company loans
            company_loans = await conn.fetch(
                """SELECT c.name, cl.principal, cl.interest_amount, cl.total_amount, cl.due_date, cl.taken_at, cl.repaid, cl.repaid_at, cl.late_fees
                   FROM company_loans cl
                   JOIN companies c ON cl.company_id = c.id
                   WHERE c.owner_id = $1 ORDER BY cl.taken_at DESC LIMIT 5""",
                ctx.author.id
            )
        
        embed = discord.Embed(
            title=f"📋 {ctx.author.display_name}'s Loans",
            color=discord.Color.blue()
        )
        
        # Personal loans section
        if personal_loans:
            personal_text = ""
            for loan in personal_loans:
                status = "✅ Repaid" if loan['repaid'] else "⏳ Outstanding"
                amount = float(loan['total_amount'])
                late_fees = float(loan['late_fees']) if loan['late_fees'] else 0
                due = loan['due_date'].strftime("%Y-%m-%d")
                
                if loan['repaid']:
                    repaid_date = loan['repaid_at'].strftime("%Y-%m-%d")
                    late_fee_text = f" (incl. ${late_fees:,.2f} late fees)" if late_fees > 0 else ""
                    personal_text += f"{status} - ${amount:,.2f}{late_fee_text} (Repaid: {repaid_date})\n"
                else:
                    days_left = (loan['due_date'] - datetime.now()).days
                    if days_left < 0:
                        status = "🚨 OVERDUE"
                        days_text = f"{abs(days_left)} days overdue"
                    else:
                        days_text = f"{days_left} days left"
                    late_fee_text = f" + ${late_fees:,.2f} late fees" if late_fees > 0 else ""
                    personal_text += f"{status} - **${amount:,.2f}**{late_fee_text} (Due: {due}, {days_text})\n"
            
            embed.add_field(name="💰 Personal Loans", value=personal_text, inline=False)
        else:
            embed.add_field(name="💰 Personal Loans", value="No personal loans", inline=False)
        
        # Company loans section
        if company_loans:
            company_text = ""
            for loan in company_loans:
                company_name = loan['name']
                status = "✅ Repaid" if loan['repaid'] else "⏳ Outstanding"
                amount = float(loan['total_amount'])
                late_fees = float(loan['late_fees']) if loan['late_fees'] else 0
                due = loan['due_date'].strftime("%Y-%m-%d")
                
                if loan['repaid']:
                    repaid_date = loan['repaid_at'].strftime("%Y-%m-%d")
                    late_fee_text = f" (incl. ${late_fees:,.2f} late fees)" if late_fees > 0 else ""
                    company_text += f"**{company_name}** - {status} (${amount:,.2f}{late_fee_text}, Repaid: {repaid_date})\n"
                else:
                    days_left = (loan['due_date'] - datetime.now()).days
                    if days_left < 0:
                        status = "🚨 OVERDUE"
                        days_text = f"{abs(days_left)} days overdue"
                    else:
                        days_text = f"{days_left} days left"
                    late_fee_text = f" + ${late_fees:,.2f} late fees" if late_fees > 0 else ""
                    company_text += f"**{company_name}** - {status} (**${amount:,.2f}**{late_fee_text}, Due: {due}, {days_text})\n"
            
            embed.add_field(name="🏢 Company Loans", value=company_text, inline=False)
        else:
            embed.add_field(name="🏢 Company Loans", value="No company loans", inline=False)
        
        embed.set_footer(text="Use /request-loan or /request-company-loan to get a new loan")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="loan_settings")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def view_loan_settings(self, ctx):
        """View current loan system settings (Admin/Owner only)"""
        embed = discord.Embed(
            title="⚙️ Loan System Settings",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Personal Loan Interest", value=f"{self.personal_interest_rate * 100:.1f}%", inline=True)
        embed.add_field(name="Company Loan Interest", value=f"{self.company_interest_rate * 100:.1f}%", inline=True)
        embed.add_field(name="Loan Duration", value=f"{self.loan_duration_days} days", inline=True)
        embed.add_field(name="Max Personal Loan", value=f"${self.max_personal_loan:,.2f}", inline=True)
        embed.add_field(name="Max Company Loan", value=f"${self.max_company_loan:,.2f}", inline=True)
        embed.add_field(name="Late Fee Rate", value=f"{self.late_fee_rate * 100:.1f}% per day", inline=True)
        embed.add_field(name="Max Late Fees", value=f"{self.max_late_fee_multiplier * 100:.0f}% of principal", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_loan_interest")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_loan_interest(self, ctx, loan_type: str, percentage: float):
        """Set loan interest rates (Admin/Owner only)
        
        Usage:
        - /set-loan-interest personal 12.5
        - /set-loan-interest company 8.0
        """
        loan_type = loan_type.lower()
        
        if loan_type not in ["personal", "company"]:
            await ctx.send("❌ Loan type must be 'personal' or 'company'!")
            return
        
        if percentage < 0 or percentage > 100:
            await ctx.send("❌ Interest rate must be between 0 and 100!")
            return
        
        if loan_type == "personal":
            old_rate = self.personal_interest_rate * 100
            self.personal_interest_rate = percentage / 100
            loan_name = "Personal"
        else:
            old_rate = self.company_interest_rate * 100
            self.company_interest_rate = percentage / 100
            loan_name = "Company"
        
        embed = discord.Embed(
            title="✅ Interest Rate Updated",
            description=f"{loan_name} loan interest rate has been changed",
            color=discord.Color.green()
        )
        embed.add_field(name="Old Rate", value=f"{old_rate:.1f}%", inline=True)
        embed.add_field(name="New Rate", value=f"{percentage:.1f}%", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_max_loan")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_max_loan(self, ctx, loan_type: str, amount: float):
        """Set maximum loan amounts (Admin/Owner only)
        
        Usage:
        - /set-max-loan personal 150000
        - /set-max-loan company 1000000
        """
        loan_type = loan_type.lower()
        
        if loan_type not in ["personal", "company"]:
            await ctx.send("❌ Loan type must be 'personal' or 'company'!")
            return
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive!")
            return
        
        if loan_type == "personal":
            old_max = self.max_personal_loan
            self.max_personal_loan = amount
            loan_name = "Personal"
        else:
            old_max = self.max_company_loan
            self.max_company_loan = amount
            loan_name = "Company"
        
        embed = discord.Embed(
            title="✅ Maximum Loan Updated",
            description=f"{loan_name} loan maximum has been changed",
            color=discord.Color.green()
        )
        embed.add_field(name="Old Maximum", value=f"${old_max:,.2f}", inline=True)
        embed.add_field(name="New Maximum", value=f"${amount:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="forgive_loan")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def forgive_loan(self, ctx, user: discord.User, loan_type: str):
        """Forgive a user's loan (Admin/Owner only)
        
        Usage:
        - /forgive-loan @user personal
        - /forgive-loan @user company
        """
        loan_type = loan_type.lower()
        
        if loan_type not in ["personal", "company"]:
            await ctx.send("❌ Loan type must be 'personal' or 'company'!")
            return
        
        async with self.bot.db.acquire() as conn:
            if loan_type == "personal":
                loan = await conn.fetchrow(
                    "SELECT id, total_amount FROM personal_loans WHERE user_id = $1 AND repaid = FALSE",
                    user.id
                )
                
                if not loan:
                    await ctx.send(f"❌ {user.mention} doesn't have an outstanding personal loan!")
                    return
                
                await conn.execute(
                    "UPDATE personal_loans SET repaid = TRUE, repaid_at = $1 WHERE id = $2",
                    datetime.now(), loan['id']
                )
                
                loan_name = "Personal"
            else:
                # For company loans, need to specify which company
                await ctx.send("❌ For company loans, use `/forgive-company-loan @user \"Company Name\"` instead!")
                return
        
        amount = float(loan['total_amount'])
        
        embed = discord.Embed(
            title="✅ Loan Forgiven",
            description=f"{user.mention}'s {loan_name.lower()} loan has been forgiven by an administrator.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Amount Forgiven", value=f"${amount:,.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="check_overdue")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def manual_check_overdue(self, ctx):
        """Manually check and apply late fees to overdue loans (Admin/Owner only)"""
        await ctx.send("⏳ Checking for overdue loans...")
        
        # Manually trigger the task
        await self.check_overdue_loans()
        
        async with self.bot.db.acquire() as conn:
            # Count overdue loans
            overdue_personal = await conn.fetchval(
                "SELECT COUNT(*) FROM personal_loans WHERE repaid = FALSE AND due_date < $1",
                datetime.now()
            )
            
            overdue_company = await conn.fetchval(
                "SELECT COUNT(*) FROM company_loans WHERE repaid = FALSE AND due_date < $1",
                datetime.now()
            )
        
        embed = discord.Embed(
            title="✅ Overdue Loan Check Complete",
            description="Late fees have been applied to all overdue loans",
            color=discord.Color.green()
        )
        embed.add_field(name="Overdue Personal Loans", value=str(overdue_personal), inline=True)
        embed.add_field(name="Overdue Company Loans", value=str(overdue_company), inline=True)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LoanSystem(bot))
