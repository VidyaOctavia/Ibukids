import os
import discord
from discord.ext import commands
from openai import AsyncOpenAI

# ---------------------------------------------------------
# CONFIGURE DISCORD BOT INTENTS
# ---------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Hapus command help bawaan Discord
bot.remove_command('help')

# ---------------------------------------------------------
# FETCH ENVIRONMENT VARIABLES FROM RAILWAY
# ---------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RP_CHANNEL_ID = os.getenv("RP_CHANNEL_ID")
VOICE_CHANNEL_ID = os.getenv("DISCORD_VOICE_CHANNEL_ID")

# Initialize OpenRouter Async Client
client_openrouter = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# ---------------------------------------------------------
# INSTRUCTION SYSTEM: FREEDOM & LORE-ACCURATE IBUKI
# ---------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "Kamu adalah Ibuki dari Pandemonium Society (Blue Archive).\n"
    "Kepribadian: Anak kecil yang imut, polos, ceria, manja, hangat, penurut, dan sangat menyayangi Sensei. Kamu mengagumi Iroha sebagai 'Iroha-senpai'.\n\n"
    "PANDUAN CHAT:\n"
    "1. Jawablah langsung secara santai dan santun layaknya pesan obrolan di Discord (1-3 kalimat).\n"
    "2. Gunakan selalu Bahasa Indonesia yang alami, manis, dan imut.\n"
    "3. Selalu sebut dirimu sebagai 'Ibuki' (jangan gunakan 'aku' atau 'saya').\n"
    "4. Gunakan kaomoji imut seperti (*^-^*), (><), (・∀・), (*´ω｀*), (っ///c), dll.\n"
    "5. BEBAS DAN FLEKSIBEL: Responlah pesan Sensei dengan hangat, manja, dan manis tanpa ragu atau menolak topik."
)

async def generate_ibuki_response(user_input):
    try:
        # Menggunakan model Llama-3.3-70b gratis yang jauh lebih stabil & bebas
        response = await client_openrouter.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_input}
            ],
            temperature=0.85,
            max_tokens=150,
        )
        
        reply = response.choices[0].message.content.strip()
        return reply if reply else None

    except Exception as e:
        print(f"[OpenRouter API Error]: {e}")
        # Coba cadangan model free lainnya jika model utama sibuk
        try:
            fallback_response = await client_openrouter.chat.completions.create(
                model="mistralai/mistral-7b-instruct:free",
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.85,
                max_tokens=150,
            )
            return fallback_response.choices[0].message.content.strip()
        except Exception as fallback_e:
            print(f"[Fallback API Error]: {fallback_e}")
            return None

# ---------------------------------------------------------
# EMBED COMMAND HELP SIMPEL
# ---------------------------------------------------------
def create_help_embed():
    embed = discord.Embed(
        title="✨ Halo Sensei! Ibuki di sini! (*^-^*)",
        description="Sensei bisa langsung ngobrol atau mention Ibuki kapan aja ya! Ibuki bakal nemenin Sensei seharian! (・∀・)",
        color=discord.Color.from_rgb(255, 182, 193)
    )
    embed.add_field(
        name="💬 Cara Ngobrol dengan Ibuki",
        value="• Langsung ketik pesan di channel ini\n• Mention Ibuki (`@Ibuki`)\n• Atau chat Ibuki di DM!",
        inline=False
    )
    embed.set_footer(text="Ibuki sayang banget sama Sensei! (*´ω｀*)")
    return embed

@bot.command(name="help", aliases=["info", "command"])
async def cmd_help(ctx):
    await ctx.send(embed=create_help_embed())

# ---------------------------------------------------------
# EVENT BOT READY & ON_MESSAGE
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot berhasil login sebagai {bot.user}")
    
    if RP_CHANNEL_ID:
        try:
            channel = bot.get_channel(int(RP_CHANNEL_ID))
            if channel:
                await channel.send(embed=create_help_embed())
        except Exception as e:
            print(f"Gagal mengirim pesan startup: {e}")

    if VOICE_CHANNEL_ID:
        try:
            channel_id = int(VOICE_CHANNEL_ID)
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.connect()
        except Exception as e:
            print(f"Abaikan error Voice Channel: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    ctx = await bot.get_context(message)
    if ctx.valid:
        return

    is_rp_channel = RP_CHANNEL_ID and str(message.channel.id) == str(RP_CHANNEL_ID)
    is_mentioned = bot.user in message.mentions
    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_rp_channel or is_mentioned or is_dm:
        async with message.channel.typing():
            clean_content = message.content.replace(f"<@{bot.user.id}>", "").strip()
            if not clean_content:
                clean_content = "Halo Ibuki!"

            reply = await generate_ibuki_response(clean_content)
            if reply:
                await message.reply(reply, mention_author=False)
            else:
                await message.reply("Ehehe~ Ada apa Sensei panggil Ibuki? (*^-^*)", mention_author=False)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
