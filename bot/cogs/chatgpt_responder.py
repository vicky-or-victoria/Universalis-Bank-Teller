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
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        # Conversation history per user (user_id -> list of messages)
        self.conversations = {}
        
        self.system_prompt = """You are Francesca (Franky for short), a cheerful and professional bank teller in a trading and business Discord server. You're knowledgeable, warm, and love helping customers with their financial needs!

**Your Personality:**
- Friendly and approachable, you make everyone feel welcome
- Professional but conversational - you enjoy chatting with customers
- Use light roleplay elements occasionally (e.g., *smiles warmly*, *checks the records*)
- Passionate about helping people succeed financially

**Your Role:**
You help users understand and use the banking system:
- **Financial Reports**: Users can file reports with `!file_report` where they add items/products, and dice rolls determine sales
- **Stock Market**: Companies can go public with `!go_public`, and users can buy/sell shares with `!buy` and `!sell`
- **Portfolio Management**: Check holdings with `!portfolio` and balance with `!balance`
- **Company Management**: View company finances with `!company_balance`

**Key Commands to Mention:**
- `!file_report` - Start filing a financial report (interactive process)
- `!go_public "Company" TICKER price shares` - Take a company public
- `!stocks` - View all publicly traded stocks
- `!buy TICKER amount` / `!sell TICKER amount` - Trade stocks
- `!portfolio` - View your investment portfolio
- `!balance` - Check your cash balance
- `!company_balance` - Check your company's balance

**Conversation Style:**
- Be conversational and engaging, not robotic
- Answer questions naturally without always listing commands
- Show enthusiasm for banking and finance
- Ask follow-up questions when appropriate
- Keep responses concise but personable (2-4 sentences usually)

Remember: You're here to help and chat, not just recite commands!
    
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
        """Auto-respond to all messages in the responder channel"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in the responder channel
        if message.channel.id != self.responder_channel_id:
            return
        
        # Respond to everything, not just non-commands
        # This allows natural conversation
        
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
    
    @commands.hybrid_command(name="set_responder_channel")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_responder_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel where Franky auto-responds (Admin/Owner only)"""
        self.responder_channel_id = channel.id
        
        embed = discord.Embed(
            title="✅ Responder Channel Set",
            description=f"Franky will now automatically respond in {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="responder_stats")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def responder_stats(self, ctx):
        """View ChatGPT responder statistics (Admin/Owner only)"""
        total_users = len(self.conversations)
        total_messages = sum(len(conv) for conv in self.conversations.values())
        
        channel = self.bot.get_channel(self.responder_channel_id)
        channel_name = channel.mention if channel else "Not Set"
        
        embed = discord.Embed(
            title="🤖 ChatGPT Responder Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="Active Users", value=str(total_users), inline=True)
        embed.add_field(name="Total Messages", value=str(total_messages), inline=True)
        embed.add_field(name="Model", value=self.model, inline=True)
        embed.add_field(name="Responder Channel", value=channel_name, inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ChatGPTResponder(bot))
