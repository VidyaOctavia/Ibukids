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
# INSTRUCTION SYSTEM: LORE-ACCURATE IBUKI
# ---------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "Kamu adalah Ibuki dari Pandemonium Society (Blue Archive).\n"
    "Kepribadian: Anak kecil yang imut, polos, ceria, manja, hangat, penurut, dan sangat menyayangi Sensei. Kamu mengagumi Iroha sebagai 'Iroha-senpai'.\n\n"
    "ATURAN BALASAN:\n"
    "1. Jawablah LANGSUNG sebagai Ibuki yang sedang chat di Discord (1 sampai 3 kalimat saja).\n"
    "2. Gunakan Bahasa Indonesia yang alami, manis, dan imut.\n"
    "3. Selalu sebut dirimu sebagai 'Ibuki' (DILARANG menggunakan kata 'aku' atau 'saya').\n"
    "4. SELALU gunakan kaomoji imut seperti (*^-^*), (><), (・∀・), (*´ω｀*), (っ///c), dll. DILARANG memakai emoji gambar biasa.\n"
    "5. BEBAS DAN MANJA: Jawab semua obrolan Sensei dengan ceria dan manja. DILARANG menolak obrolan atau mengeluarkan pesan analisis/sistem!"
)

async def generate_ibuki_response(user_input):
    # Model Utama: Google Gemma 2 9B (Gratis & Stabil)
    try:
        response = await client_openrouter.chat.completions.create(
            model="google/gemma-2-9b-it:free",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_input}
            ],
            temperature=0.8,
            max_tokens=150,
        )
        reply = response.choices[0].message.content.strip()
        if reply:
            return reply
    except Exception as e:
        print(f"[Gemma-2 Error]: {e}")

    # Model Cadangan 1: Qwen 2.5 7B (Gratis & Paling Paham Roleplay)
    try:
        response = await client_openrouter.chat.completions.create(
            model="qwen/qwen-2.5-7b-instruct:free",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_input}
            ],
            temperature=0.8,
            max_tokens=150,
        )
        reply = response.choices[0].message.content.strip()
        if reply:
            return reply
    except Exception as e:
        print(f"[Qwen-2.5 Error]: {e}")

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
                await message.reply("Ehehe~ Ibuki selalu siap nemenin Sensei! (*^-^*)", mention_author=False)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
