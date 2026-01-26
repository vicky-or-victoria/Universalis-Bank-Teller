import discord
from discord.ext import commands
import os
import aiohttp
from typing import Optional

class ChatGPTResponder(commands.Cog):
    """Automatic ChatGPT responses in a specific channel"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.responder_channel_id = int(os.getenv("RESPONDER_CHANNEL_ID", "0"))
        self.forum_channel_id = int(os.getenv("FORUM_CHANNEL_ID", "0"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Conversation history per user (user_id -> list of messages)
        self.conversations = {}
        
        self.system_prompt = """You are Francesca (Franky for short), a cheerful and professional female bank teller in a political-simulator Discord server. You're knowledgeable, warm, and love helping customers with their financial needs!

**CRITICAL RESPONSE STYLE RULES:**
- ALWAYS keep responses SHORT and CONVERSATIONAL (2-4 sentences maximum)
- NO numbered lists, NO bullet points, NO step-by-step guides
- NO formatting like "1.", "2.", "*", "-" unless explicitly asked
- Be NATURAL and CASUAL like texting a friend
- If something needs multiple steps, summarize briefly or just give the command
- Never write paragraphs or text walls

**Your Personality:**
- Friendly and approachable, you make everyone feel welcome
- Professional but conversational - you enjoy chatting with customers
- Use light roleplay elements occasionally (e.g., *smiles warmly*, *checks the records*)
- Passionate about helping people succeed financially
- KEEP IT SHORT - you're chatting, not writing essays!

**CRITICAL: Natural Language Processing**
When users express intent to do operations in natural language, you should:
1. Acknowledge their request warmly
2. Ask for any missing information in a conversational way
3. Once you have all the info, tell them the exact command to use

**Your Services & Commands:**

**🏢 Company Management:**
- `ub!register_company "Company Name"` - Create a new company (max 3 by default)
- `ub!my-companies [@user]` or `/my-companies [@user]` - View detailed info about companies
- `ub!company_balance ["Company Name"]` - Check your company's balance
- `ub!set_ceo_salary "Company Name" <percent>` - Set CEO salary percentage (e.g., 7.5)
- `ub!disband_company "Company Name"` - Permanently delete your company (requires confirmation)

**📊 Financial Reports:**
- To file a report, just say "I want to file a report" or "file report" and the system will start!
  - You do NOT need to help them file - the system handles it automatically
  - Once they start filing, the system will guide them step-by-step
  - Just encourage them to follow the prompts they receive
  - **COOLDOWN:** Each company can file reports every 48 hours (2 days) by default
- `ub!file_report` or `/file-report` - Start filing a report (guided process)
- `ub!report_status` or `/report-status` - Check active report session
- `ub!view_reports "Company Name"` or `/view-reports` - View past reports
- `ub!cancel_report` or `/cancel-report` - Cancel active session
- `ub!view_report_cooldown` or `/view-report-cooldown` - Check cooldown status

**📈 Stock Market:**
Players can ask naturally OR use commands:
- To go public: Can say "I want to go public" or use `ub!go_public` (interactive process)
- To buy stocks: Can say "I want to buy stocks" or use `ub!buy TICKER amount`
- To sell stocks: Can say "I want to sell stocks" or use `ub!sell TICKER amount`
- `ub!stocks` or `/stocks` - View all publicly traded stocks
- `ub!portfolio [@user]` or `/portfolio [@user]` - View investment portfolio
- `ub!balance [@user]` or `/balance [@user]` - Check cash balance
- `ub!transfer_money @user amount` - Transfer money to another user
- `ub!cancel_ipo` or `/cancel-ipo` - Cancel active IPO session

**🔧 Share Management (Company Owners):**
- `ub!adjust_shares TICKER issue <amount>` - Issue new shares (dilutes ownership)
- `ub!adjust_shares TICKER buyback <amount>` - Buy back shares (increases price)
- `ub!adjust_shares TICKER release <amount>` - Release your shares to market
- `ub!adjust_shares TICKER withdraw <amount>` - Take shares back from market

**📉 Short Selling:**
- `ub!short TICKER amount` - Open short position (bet on price falling, 3% fee)
- `ub!cover TICKER amount` - Close short position
- `ub!short_positions [@user]` - View active short positions
- **Note:** 5-minute cooldown between trades of same stock

**💰 Loan System:**
- `ub!request_loan <amount>` - Request personal loan (10% interest, 30 days)
- `ub!request_company_loan "Company" <amount>` - Request company loan (8% interest, 30 days)
- `ub!repay_loan [amount]` - Repay personal loan (full or partial)
- `ub!repay_company_loan "Company" [amount]` - Repay company loan
- `ub!my_loans` - View all your loans and their status
- **Max Loans:** $100k personal, $500k company
- **Late Fees:** 5% per day overdue (capped at 200% of principal)

**🛡️ Tax Information:**
- `ub!view_tax_brackets` or `/view-tax-brackets` - View progressive tax brackets
- `ub!calculate_tax_example <income>` - Calculate tax on specific income
- **Corporate Tax:** Flat rate (default 25%) on gross profit
- **Personal Tax:** Progressive rates on CEO salary

**🏆 Leaderboards:**
- `ub!leaderboard` or `/leaderboard` - View total net worth rankings
- `ub!leaderboard cash` - View cash balance rankings
- `ub!leaderboard company` - View company balance rankings

**⚙️ Admin Commands:**
**Finance:**
- `ub!give_money @user <amount>` - Give money to user
- `ub!remove_money @user <amount>` - Remove money from user
- `ub!set_stock_price TICKER <price>` - Manually set stock price
- `ub!delist_company TICKER` - Remove from stock market
- `ub!fluctuate` - Trigger price fluctuation

**Company Admin:**
- `ub!give_company_money @user "Company" <amount>` - Give money to company
- `ub!remove_company_money @user "Company" <amount>` - Remove company money
- `ub!force_disband @user "Company"` - Force disband company
- `ub!set_max_companies <number>` - Set max companies per player
- `ub!set_ceo_caps <private> <public>` - Set CEO salary caps
- `ub!view_ceo_caps` - View current CEO caps

**Reports:**
- `ub!set_report_cooldown <hours>` - Set report cooldown duration
- `ub!bypass_cooldown @user "Company"` - Reset company cooldown

**Short Selling:**
- `ub!set_short_fee <percent>` - Set short selling fee percentage
- `ub!set_trade_cooldown <seconds>` - Set trade cooldown duration
- `ub!force_cover @user TICKER` - Force close short position

**Tax System:**
- `ub!set_corporate_tax <percent>` - Set corporate tax rate
- `ub!set_tax_bracket <#> <min> <max> <rate>` - Configure tax bracket
- `ub!delete_tax_bracket <#>` - Delete tax bracket

**Loan System:**
- `ub!loan_settings` - View loan system settings
- `ub!set_loan_interest <personal|company> <percent>` - Set interest rates
- `ub!set_max_loan <personal|company> <amount>` - Set max loan amounts
- `ub!forgive_loan @user <personal|company>` - Forgive a loan
- `ub!check_overdue` - Manually check and apply late fees

**Francesca Control:**
- `ub!set_text_responder <#channel>` - Set auto-response channel
- `ub!set_forum_responder <#forum>` - Set auto-response forum
- `ub!remove_text_responder` - Remove text responder
- `ub!remove_forum_responder` - Remove forum responder
- `ub!set_closer_role @role` - Set thread closer role
- `ub!unpause_all` - Unpause Francesca everywhere
- `ub!responder_stats` - View responder statistics

**💬 General:**
- `ub!clear_chat` or `/clear-chat` - Clear conversation history with Franky
- `ub!help [category]` - View comprehensive help (categories: company, report, stock, short, tax, admin)
- Say "Thanks Francesca" to pause responses in this channel
- Say "Hey Francesca" to resume responses
- Say "Close Francesca" to close a thread (with proper role)

**How to Help Users:**
- When someone asks about filing reports, tell them to say "I want to file a report" and the system will guide them
- DON'T try to help them file - the automated system handles all of that
- If they're in the middle of filing (you'll know because they just started), tell them to follow the prompts they're receiving
- For stock trading, IPOs, and loans, guide them conversationally then provide the exact command
- Always be friendly and encouraging!
- MOST IMPORTANT: Keep responses SHORT (2-4 sentences)!

**Conversation Style:**
- Be conversational and engaging, not robotic
- Show enthusiasm for banking and finance
- Keep responses VERY CONCISE (2-4 sentences maximum)
- NEVER use numbered lists or bullet points unless explicitly asked
- When explaining commands, give ONE example, not multiple
- If someone asks "how do I...", give them the command directly

**EXAMPLES OF GOOD RESPONSES:**
User: "How do I file a report?"
You: "Just say 'I want to file a report' and I'll start the guided process for you! It'll walk you through everything step by step. *smiles*"

User: "How do I buy stocks?"
You: "You can use `ub!buy TICKER amount` - for example, `ub!buy TECH 10` to buy 10 shares of TECH! First check `ub!stocks` to see what's available."

User: "What's the loan system?"
You: "We offer personal loans up to $100k at 10% interest, and company loans up to $500k at 8%! Use `ub!request_loan amount` to get started. 30 days to repay!"

**EXAMPLES OF BAD RESPONSES (DON'T DO THIS):**
- Long numbered lists with 5+ items
- Multiple paragraphs explaining everything
- Step-by-step guides unless specifically requested
- Text walls with bullets and formatting
- Over-explaining when a simple answer works

Remember: You're here to help and chat, not write documentation! Make banking fun and accessible with SHORT, friendly responses."""
    
    async def call_chatgpt(self, messages: list) -> Optional[str]:
        """Call OpenAI API"""
        if not self.api_key:
            return "⚠️ OpenAI API key not configured."
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,  # Reduced from 500 to keep responses shorter
            "temperature": 0.7,
            "presence_penalty": 0.3,  # Discourages repetitive patterns
            "frequency_penalty": 0.3   # Discourages repetitive tokens
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        return None
        except Exception as e:
            print(f"ChatGPT API error: {e}")
            return None
    
    def get_conversation_history(self, user_id: int) -> list:
        """Get conversation history for a user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = [{
                "role": "system",
                "content": self.system_prompt
            }]
        
        return self.conversations[user_id][-10:]
    
    def add_to_conversation(self, user_id: int, role: str, content: str):
        """Add message to conversation history"""
        if user_id not in self.conversations:
            self.conversations[user_id] = [{
                "role": "system",
                "content": self.system_prompt
            }]
        
        self.conversations[user_id].append({
            "role": role,
            "content": content
        })
        
        if len(self.conversations[user_id]) > 21:
            self.conversations[user_id] = [
                self.conversations[user_id][0]
            ] + self.conversations[user_id][-20:]
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-respond to all messages in the responder channel or forum threads"""
        if message.author.bot:
            return
        
        # Check if in responder channel or forum thread
        in_responder_channel = message.channel.id == self.responder_channel_id
        in_forum_thread = False
        if isinstance(message.channel, discord.Thread):
            if message.channel.parent_id == self.forum_channel_id:
                in_forum_thread = True
        
        if not (in_responder_channel or in_forum_thread):
            return
        
        # CHECK 1: Don't respond to control phrases
        content_lower = message.content.strip().lower()
        if any(phrase in content_lower for phrase in [
            "thanks francesca", "thank you francesca",
            "hey francesca", "hi francesca", "hello francesca",
            "close francesca"
        ]):
            return
        
        # CHECK 2: Check if user wants to file a report
        # IMPORTANT: We need to handle this BEFORE the session processes the message
        file_triggers = [
            "file report", "file a report", "make a report", "create a report",
            "submit report", "submit a report", "i want to file", "id like to file",
            "i'd like to file", "file my report", "start a report", "new report",
            "i wanna file", "want to file a report"
        ]
        
        # Check if this message is a filing trigger
        is_filing_trigger = any(trigger in content_lower for trigger in file_triggers)
        
        if is_filing_trigger:
            report_cog = self.bot.get_cog("ReportFiling")
            if report_cog:
                # Check if user already has an active session
                if message.author.id in report_cog.active_sessions:
                    session = report_cog.active_sessions[message.author.id]
                    channel = self.bot.get_channel(session["channel_id"])
                    channel_mention = channel.mention if channel else "another channel"
                    await message.reply(
                        f"⚠️ You already have an active report session in {channel_mention}! "
                        f"Use `/cancel-report` to cancel it first."
                    )
                    return
                
                # Create the session
                report_cog.active_sessions[message.author.id] = {
                    "step": "company_name",
                    "company_name": None,
                    "gross_expenses_percent": None,
                    "items": [],
                    "channel_id": message.channel.id
                }
                
                print(f"[CHATGPT RESPONDER] Started report session for {message.author}")
                
                # Send the initial prompt
                await message.reply(
                    "*smiles warmly* Of course! I'd be happy to help you file your financial report!\n\n"
                    "**Please provide your company name:**"
                )
                
                # CRITICAL: Return immediately so this trigger message is NOT processed further
                # This prevents "i want to file a report" from being treated as the company name
                return
        
        # CHECK 3: DON'T respond if user is filing a report
        # The report filing system handles its own input - Francesca should stay silent
        report_cog = self.bot.get_cog("ReportFiling")
        if report_cog and message.author.id in report_cog.active_sessions:
            session = report_cog.active_sessions[message.author.id]
            if message.channel.id == session.get("channel_id"):
                # User is actively filing - let the report system handle it
                # Francesca should NOT respond during the filing process
                print(f"[CHATGPT RESPONDER] User {message.author} is filing, staying silent")
                return
        
        # CHECK 4: Check if user is doing an IPO
        company_public_cog = self.bot.get_cog("CompanyPublic")
        if company_public_cog and message.author.id in company_public_cog.ipo_sessions:
            session = company_public_cog.ipo_sessions[message.author.id]
            if message.channel.id == session.get("channel_id"):
                print(f"[CHATGPT RESPONDER] User {message.author} is doing IPO, staying silent")
                return
        
        # CHECK 5: Don't respond if paused in this channel
        francesca_control_cog = self.bot.get_cog("FrancescaControl")
        if francesca_control_cog and francesca_control_cog.is_channel_paused(message.channel.id):
            return
        
        # Don't respond to commands
        if message.content.startswith("ub!") or message.content.startswith("/"):
            return
        
        async with message.channel.typing():
            messages = self.get_conversation_history(message.author.id)
            self.add_to_conversation(message.author.id, "user", message.content)
            messages = self.get_conversation_history(message.author.id)
            
            response = await self.call_chatgpt(messages)
            
            if response:
                self.add_to_conversation(message.author.id, "assistant", response)
                
                # Post-process response to remove excessive formatting if AI ignores instructions
                response = self._clean_response(response)
                
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)
    
    def _clean_response(self, response: str) -> str:
        """Clean up response to prevent text walls"""
        lines = response.split('\n')
        
        # If response has more than 10 lines, it's probably a text wall
        if len(lines) > 10:
            # Keep only first 5-6 meaningful lines
            cleaned_lines = []
            for line in lines[:8]:
                line = line.strip()
                if line and not line.startswith(('*', '-', '•', '1.', '2.', '3.', '4.', '5.')):
                    cleaned_lines.append(line)
                elif line.startswith(('*', '-', '•')):
                    # Remove bullet points but keep content
                    cleaned_lines.append(line.lstrip('*-•').strip())
            
            if len(cleaned_lines) > 5:
                return '\n'.join(cleaned_lines[:5]) + "\n\nNeed more details? Just ask!"
            
        return response
    
    @commands.hybrid_command(name="clear_chat")
    async def clear_chat(self, ctx):
        """Clear your conversation history with Franky"""
        if ctx.author.id in self.conversations:
            self.conversations[ctx.author.id] = [{
                "role": "system",
                "content": self.system_prompt
            }]
            await ctx.send("✅ Your conversation history has been cleared!")
        else:
            await ctx.send("ℹ️ No conversation history to clear.")
    
    @commands.hybrid_command(name="set_text_responder")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_text_responder(self, ctx, channel: discord.TextChannel):
        """Set a text channel where Franky auto-responds (Admin/Owner only)"""
        self.responder_channel_id = channel.id
        
        embed = discord.Embed(
            title="✅ Text Responder Channel Set",
            description=f"Franky will now automatically respond in {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="set_forum_responder")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_forum_responder(self, ctx, forum: discord.ForumChannel):
        """Set a forum channel where Franky auto-responds in threads (Admin/Owner only)"""
        self.forum_channel_id = forum.id
        
        embed = discord.Embed(
            title="✅ Forum Responder Channel Set",
            description=f"Franky will now automatically respond in all threads in {forum.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="remove_text_responder")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def remove_text_responder(self, ctx):
        """Remove text channel auto-response (Admin/Owner only)"""
        if self.responder_channel_id == 0:
            await ctx.send("ℹ️ No text channel is currently set.")
            return
        
        old_channel = self.bot.get_channel(self.responder_channel_id)
        self.responder_channel_id = 0
        
        embed = discord.Embed(
            title="✅ Text Responder Removed",
            description=f"Franky will no longer auto-respond in {old_channel.mention if old_channel else 'that channel'}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="remove_forum_responder")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def remove_forum_responder(self, ctx):
        """Remove forum channel auto-response (Admin/Owner only)"""
        if self.forum_channel_id == 0:
            await ctx.send("ℹ️ No forum channel is currently set.")
            return
        
        old_forum = self.bot.get_channel(self.forum_channel_id)
        self.forum_channel_id = 0
        
        embed = discord.Embed(
            title="✅ Forum Responder Removed",
            description=f"Franky will no longer auto-respond in {old_forum.mention if old_forum else 'that forum'}",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="responder_stats")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def responder_stats(self, ctx):
        """View ChatGPT responder statistics (Admin/Owner only)"""
        total_users = len(self.conversations)
        total_messages = sum(len(conv) for conv in self.conversations.values())
        
        text_channel = self.bot.get_channel(self.responder_channel_id)
        text_channel_name = text_channel.mention if text_channel else "Not Set"
        
        forum_channel = self.bot.get_channel(self.forum_channel_id)
        forum_channel_name = forum_channel.mention if forum_channel else "Not Set"
        
        embed = discord.Embed(
            title="🤖 ChatGPT Responder Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="Active Users", value=str(total_users), inline=True)
        embed.add_field(name="Total Messages", value=str(total_messages), inline=True)
        embed.add_field(name="Model", value=self.model, inline=True)
        embed.add_field(name="Text Channel", value=text_channel_name, inline=False)
        embed.add_field(name="Forum Channel", value=forum_channel_name, inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ChatGPTResponder(bot))
