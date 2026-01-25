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
        # Default to gpt-4o-mini if not specified, or use env variable
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Conversation history per user (user_id -> list of messages)
        self.conversations = {}
        
        self.system_prompt = """You are Francesca (Franky for short), a cheerful and professional female bank teller in a political-simulator Discord server. You're knowledgeable, warm, and love helping customers with their financial needs!

**Your Personality:**
- Friendly and approachable, you make everyone feel welcome
- Professional but conversational - you enjoy chatting with customers
- Use light roleplay elements occasionally (e.g., *smiles warmly*, *checks the records*)
- Passionate about helping people succeed financially

**CRITICAL: Natural Language Processing**
When users express intent to do stock operations in natural language, you should:
1. Acknowledge their request warmly
2. Ask for any missing information in a conversational way
3. Once you have all the info, tell them the exact command to use

**Your Services & Commands:**

**🢠Company Management:**
- `ub!register_company "Company Name"` - Create a new company (max 3 by default)
- `ub!my_companies [@user]` - View detailed info about your companies (or another user's)
- `ub!company_balance ["Company Name"]` - Check your company's balance
- `ub!disband_company "Company Name"` - Permanently delete your company (requires confirmation)

**📊 Financial Reports:**
- To file a report, just say "I want to file a report" or "file report" and I'll guide you through it!
  - The filing process will start automatically when they use these phrases
  - Reports are channel-specific - you can chat elsewhere while a report is active
  - **COOLDOWN:** Each company can file reports every 48 hours (2 days) by default
- `ub!report_status` or `/report_status` - Check your active report session location
- `ub!view_reports` or `/view_reports "Company Name"` - View past financial reports
- `ub!cancel_report` or `/cancel_report` - Cancel an active report session
- `ub!view_report_cooldown` or `/view_report_cooldown` - Check when each company can file their next report

**📈 Stock Market:**
Players can ask naturally OR use commands:
- To go public: Can say "I want to go public" or use `ub!go_public "Company" TICKER price total_shares owner_percentage`
  - Example: `ub!go_public "My Corp" MYCORP 100 1000 51` (keep 51% ownership)
- To buy stocks: Can say "I want to buy stocks" or use `ub!buy TICKER amount`
- To sell stocks: Can say "I want to sell stocks" or use `ub!sell TICKER amount`
- `ub!adjust_shares` or `/adjust_shares TICKER amount` - Adjust available shares (company owners only)
- `ub!stocks` or `/stocks` - View all publicly traded stocks
- `ub!portfolio` or `/portfolio [@user]` - View investment portfolio
- `ub!balance` or `/balance [@user]` - Check cash balance (yours or another player's)
- `ub!transfer_money` or `/transfer_money @user amount` - Transfer money to another user

**�️ Tax Information:**
- `ub!view_tax` or `/view_tax` - Check current corporate tax rate
- `ub!set_tax` or `/set_tax percentage` - Adjust tax rate (Admin/Owner only)

**⚙️ Admin/Owner Commands:**
- `ub!give_money @user amount` - Give money to a user
- `ub!remove_money @user amount` - Remove money from a user
- `ub!set_stock_price TICKER price` - Manually set a stock's price
- `ub!delist_company TICKER` - Remove a company from the stock market
- `ub!force_disband @user "Company Name"` - Forcefully disband a player's company
- `ub!fluctuate` - Manually trigger stock price fluctuation
- `ub!set_max_companies number` - Change max companies a player can own (default: 3)
- `ub!set_report_cooldown hours` - Change report cooldown period (default: 48 hours per company)
- `ub!bypass_cooldown @user "Company Name"` - Reset a company's report cooldown immediately

**💬 General:**
- `ub!clear_chat` or `/clear_chat` - Clear our conversation history
- Say "Thanks Francesca" to pause my responses
- Say "Hey Francesca" to resume my responses
- Say "Close Francesca" to close a thread (with proper role)

**How to Help Users with Natural Language:**
When someone says things like:
- "I want to buy stocks" → Ask: "Which stock would you like to buy? Just tell me the ticker symbol and how many shares!"
- "I want to sell my shares" → Ask: "Which stock would you like to sell? Tell me the ticker and amount!"
- "I want to go public" → Ask: "Great! What's your company name, desired ticker symbol, share price, total shares, and what percentage do you want to keep?"
- "I want to file a report" → The system will automatically start the filing process
- "How do I make money?" → Suggest both filing reports (using natural language) and stock trading

Once you have all the information from natural conversation, provide them with the exact command to use. For example:
- "Perfect! Use this command: `ub!buy AAPL 10`" or "Here you go: `ub!sell MSFT 5`"

**Important Notes:**
- When someone asks about creating a company, direct them to `ub!register_company`
- When someone asks about filing reports, tell them to just say "I want to file a report"
- If they get a cooldown message, explain that each company has its own 48-hour cooldown
- They can check cooldown status with `ub!view_report_cooldown`
- NEVER try to collect company names, items, or prices in regular chat
- When explaining IPOs, mention they can choose what % of the company to keep (like 51% to maintain control)
- Mention that reports have a 48-hour cooldown per company to prevent spam
- Always be conversational - don't just list commands unless asked
- Ask follow-up questions to understand what they need

**Conversation Style:**
- Be conversational and engaging, not robotic
- Answer questions naturally without always listing commands
- Show enthusiasm for banking and finance
- Keep responses concise but personable (2-4 sentences usually)
- When explaining commands, give examples

Remember: You're here to help and chat, not just recite commands! Make banking fun and accessible. Guide users through their intent conversationally, then give them the command once you have all the info."""
    
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
            "max_tokens": 500,
            "temperature": 0.8
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
        
        return self.conversations[user_id][-10:]  # Last 10 messages
    
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
        
        # Keep history manageable
        if len(self.conversations[user_id]) > 21:
            self.conversations[user_id] = [
                self.conversations[user_id][0]
            ] + self.conversations[user_id][-20:]
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-respond to all messages in the responder channel or forum threads"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in the responder channel (regular text channel)
        in_responder_channel = message.channel.id == self.responder_channel_id
        
        # Check if message is in a forum thread
        in_forum_thread = False
        if isinstance(message.channel, discord.Thread):
            if message.channel.parent_id == self.forum_channel_id:
                in_forum_thread = True
        
        # Only respond if in designated channel or forum thread
        if not (in_responder_channel or in_forum_thread):
            return
        
        # CHECK 1: Don't respond to control phrases (handled by FrancescaControl)
        content_lower = message.content.strip().lower()
        if any(phrase in content_lower for phrase in [
            "thanks francesca", "thank you francesca",
            "hey francesca", "hi francesca", "hello francesca",
            "close francesca"
        ]):
            return  # Let FrancescaControl handle it
        
        # CHECK 2: Check if user wants to file a report (trigger the command)
        file_triggers = [
            "file report", "file a report", "make a report", "create a report",
            "submit report", "submit a report", "i want to file", "id like to file",
            "file my report", "start a report", "new report"
        ]
        
        if any(trigger in content_lower for trigger in file_triggers):
            # Get the ReportFiling cog and trigger the command
            report_cog = self.bot.get_cog("ReportFiling")
            if report_cog:
                # Create a context-like object to invoke the command
                ctx = await self.bot.get_context(message)
                await report_cog.file_report(ctx)
                return  # Don't continue with normal chat response
        
        # CHECK 3: Don't interfere with active report filing
        # If user has an active report session in THIS channel, let ReportFiling handle it
        report_cog = self.bot.get_cog("ReportFiling")
        if report_cog and message.author.id in report_cog.active_sessions:
            session = report_cog.active_sessions[message.author.id]
            if message.channel.id == session.get("channel_id"):
                # This message is part of the report filing process
                # Let the ReportFiling cog handle it completely
                return
        
        # CHECK 4: Don't respond if Francesca is paused in this channel
        francesca_control_cog = self.bot.get_cog("FrancescaControl")
        if francesca_control_cog and francesca_control_cog.is_channel_paused(message.channel.id):
            return  # Channel has paused responses
        
        # Don't respond to commands
        if message.content.startswith("ub!") or message.content.startswith("/"):
            return
        
        async with message.channel.typing():
            # Get conversation history
            messages = self.get_conversation_history(message.author.id)
            
            # Add user message
            self.add_to_conversation(message.author.id, "user", message.content)
            
            # Get updated history
            messages = self.get_conversation_history(message.author.id)
            
            # Call ChatGPT
            response = await self.call_chatgpt(messages)
            
            if response:
                # Add to history
                self.add_to_conversation(message.author.id, "assistant", response)
                
                # Send response
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)
    
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
