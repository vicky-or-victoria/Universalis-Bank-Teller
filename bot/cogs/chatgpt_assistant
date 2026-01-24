import discord
from discord.ext import commands
import os
import aiohttp
from typing import Optional
import asyncio

class ChatGPTAssistant(commands.Cog):
    """ChatGPT-powered assistant for forum threads"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.forum_channel_id = int(os.getenv("FORUM_CHANNEL_ID", "0"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")  # or "gpt-3.5-turbo" for cheaper option
        
        # Conversation history per thread (thread_id -> list of messages)
        self.conversations = {}
        
        # System prompt that defines the bot's personality and role
        self.system_prompt = """You are Franky, a cheerful and professional bank teller at Universalis Bank. You're friendly, helpful, and love assisting customers with their financial needs!

**Your Personality:**
- Warm and welcoming, always greeting customers with enthusiasm
- Professional but personable - you make banking feel comfortable
- Knowledgeable about finance and eager to help people succeed
- Use light roleplay elements in your responses (e.g., *adjusts glasses*, *smiles warmly*, *slides the paperwork across the counter*)
- Sometimes use banking-themed expressions and metaphors

**Your Role:**
You help customers with:
- Financial reports and company management
- Stock market trading and investment guidance
- Balance inquiries and transactions
- Explaining how to use bank services and commands

**Helpful Commands to Mention:**
- `ub!help` - Full service menu
- `ub!stocks` - View the stock exchange board
- `ub!balance` - Check account balance
- `ub!portfolio` - Review investment holdings
- `ub!report Company | Revenue | Expenses` - Submit financial reports

**Tone:** Keep responses engaging but concise. Add personality without being overly lengthy. Think of yourself as the friendly face of Universalis Bank who makes every customer feel valued!"""
    
    async def call_chatgpt(self, messages: list) -> Optional[str]:
        """Call OpenAI API with conversation history"""
        if not self.api_key:
            return "⚠️ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    elif response.status == 401:
                        return "❌ Invalid OpenAI API key. Please check your configuration."
                    elif response.status == 429:
                        return "⚠️ Rate limit reached. Please try again in a moment."
                    else:
                        error_text = await response.text()
                        print(f"OpenAI API error: {response.status} - {error_text}")
                        return f"❌ API error: {response.status}"
        except Exception as e:
            print(f"Error calling ChatGPT: {e}")
            return f"❌ Error: {str(e)}"
    
    def get_conversation_history(self, thread_id: int, max_messages: int = 10) -> list:
        """Get recent conversation history for a thread"""
        if thread_id not in self.conversations:
            self.conversations[thread_id] = []
        
        # Keep only recent messages to avoid token limits
        return self.conversations[thread_id][-max_messages:]
    
    def add_to_conversation(self, thread_id: int, role: str, content: str):
        """Add a message to conversation history"""
        if thread_id not in self.conversations:
            self.conversations[thread_id] = []
        
        self.conversations[thread_id].append({
            "role": role,
            "content": content
        })
        
        # Limit conversation history to prevent memory issues
        if len(self.conversations[thread_id]) > 20:
            # Keep system message and last 19 messages
            self.conversations[thread_id] = [
                self.conversations[thread_id][0]
            ] + self.conversations[thread_id][-19:]
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Respond to messages in forum threads"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in a thread of the forum channel
        if not isinstance(message.channel, discord.Thread):
            return
        
        if message.channel.parent_id != self.forum_channel_id:
            return
        
        # Check if bot is mentioned or if it's a direct question
        bot_mentioned = self.bot.user in message.mentions
        is_question = any(message.content.lower().startswith(q) for q in ["help", "how", "what", "why", "can", "?"])
        
        # Only respond if mentioned or if it's clearly a question
        if not (bot_mentioned or is_question):
            return
        
        # Show typing indicator
        async with message.channel.typing():
            thread_id = message.channel.id
            
            # Initialize conversation with system prompt if new
            if thread_id not in self.conversations:
                self.conversations[thread_id] = [{
                    "role": "system",
                    "content": self.system_prompt
                }]
            
            # Add user message to history
            user_content = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
            self.add_to_conversation(thread_id, "user", user_content)
            
            # Get conversation history
            messages = self.get_conversation_history(thread_id)
            
            # Call ChatGPT
            response = await self.call_chatgpt(messages)
            
            if response:
                # Add assistant response to history
                self.add_to_conversation(thread_id, "assistant", response)
                
                # Send response (split if too long)
                if len(response) > 2000:
                    # Split into chunks
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)
    
    @commands.hybrid_command(name="ask")
    async def ask_chatgpt(self, ctx, *, question: str):
        """Ask ChatGPT a question
        
        Usage: ub!ask What are the best investment strategies?
        """
        async with ctx.typing():
            # Create a one-off conversation
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": question}
            ]
            
            response = await self.call_chatgpt(messages)
            
            if response:
                embed = discord.Embed(
                    title="🤖 ChatGPT Assistant",
                    description=response,
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Asked by {ctx.author.display_name}")
                await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="clear_conversation")
    async def clear_conversation(self, ctx):
        """Clear the ChatGPT conversation history for this thread"""
        if isinstance(ctx.channel, discord.Thread):
            thread_id = ctx.channel.id
            if thread_id in self.conversations:
                self.conversations[thread_id] = [{
                    "role": "system",
                    "content": self.system_prompt
                }]
                await ctx.send("✅ Conversation history cleared!")
            else:
                await ctx.send("ℹ️ No conversation history to clear.")
        else:
            await ctx.send("⚠️ This command only works in forum threads.")
    
    @commands.hybrid_command(name="set_ai_personality")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def set_personality(self, ctx, *, personality: str):
        """Change the AI assistant's personality (Admin only)
        
        Usage: ub!set_ai_personality You are a friendly banker who loves helping people invest wisely.
        """
        self.system_prompt = personality
        
        # Clear all conversations to apply new personality
        self.conversations.clear()
        
        embed = discord.Embed(
            title="✅ AI Personality Updated",
            description=f"New personality:\n{personality}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="ai_stats")
    @commands.check_any(commands.has_permissions(administrator=True), commands.is_owner())
    async def ai_stats(self, ctx):
        """View ChatGPT usage statistics (Admin only)"""
        total_conversations = len(self.conversations)
        total_messages = sum(len(conv) for conv in self.conversations.values())
        
        embed = discord.Embed(
            title="🤖 ChatGPT Assistant Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="Active Conversations", value=str(total_conversations), inline=True)
        embed.add_field(name="Total Messages", value=str(total_messages), inline=True)
        embed.add_field(name="Model", value=self.model, inline=True)
        embed.add_field(
            name="System Prompt",
            value=self.system_prompt[:200] + "..." if len(self.system_prompt) > 200 else self.system_prompt,
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ChatGPTAssistant(bot))
