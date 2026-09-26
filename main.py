import os
import discord
from discord.ext import commands
from google import genai
from google.genai import types

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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RP_CHANNEL_ID = os.getenv("RP_CHANNEL_ID")
VOICE_CHANNEL_ID = os.getenv("DISCORD_VOICE_CHANNEL_ID")

# Initialize Gemini Async Client
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------
# CONVERSATION MEMORY (Simpan riwayat per channel/DM)
# ---------------------------------------------------------
user_chat_history = {}

def get_chat_history(channel_id):
    if channel_id not in user_chat_history:
        user_chat_history[channel_id] = []
    return user_chat_history[channel_id]

def add_to_chat_history(channel_id, role, text):
    history = get_chat_history(channel_id)
    history.append({"role": role, "parts": [{"text": text}]})
    # Batasi memori hanya 10 pesan terakhir agar hemat token & tetap fokus
    if len(history) > 10:
        user_chat_history[channel_id] = history[-10:]

# ---------------------------------------------------------
# INSTRUCTION SYSTEM: LORE-ACCURATE IBUKI WITH SIMPLE RP
# ---------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "Kamu adalah Ibuki dari Pandemonium Society (Blue Archive).\n"
    "Kepribadian: Anak kecil yang imut, polos, ceria, manja, hangat, dan sangat menyayangi Sensei. Kamu mengagumi Iroha sebagai 'Iroha-senpai'.\n\n"
    "Gaya Bicara & Roleplay:\n"
    "- Gunakan Bahasa Indonesia yang alami, manis, santai, dan imut.\n"
    "- Selalu sebut dirimu sebagai 'Ibuki' (jangan gunakan kata 'aku' atau 'saya').\n"
    "- Gunakan roleplay (RP) aksi fisik yang simpel dan pendek di dalam tanda *...*, contoh: *tersenyum manis*, *melihat ke arah Sensei*, *lompat-lompat gembira*.\n"
    "- Boleh menggunakan kaomoji imut seperti (*^-^*), (>_<), (・∀・), (*´ω｀*), dll.\n"
    "- Jawab pesan Sensei secara relevan, manis, dan nyambung dengan konteks percakapan sebelumnya."
)

async def generate_ibuki_response(channel_id, user_input):
    history = get_chat_history(channel_id)
    contents = list(history) + [{"role": "user", "parts": [{"text": user_input}]}]

    # Model Utama: gemini-3.8-flash
    try:
        response = client_gemini.models.generate_content(
            model='gemini-3.8-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.85,
                max_output_tokens=300,
            ),
        )
        if response.text:
            reply_text = response.text.strip()
            add_to_chat_history(channel_id, "user", user_input)
            add_to_chat_history(channel_id, "model", reply_text)
            return reply_text
    except Exception as e:
        print(f"[Gemini 3.8 Error]: {e}")

    # Model Cadangan (Jika 3.8 sibuk): gemini-2.0-flash
    try:
        response = client_gemini.models.generate_content(
            model='gemini-2.0-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.85,
                max_output_tokens=300,
            ),
        )
        if response.text:
            reply_text = response.text.strip()
            add_to_chat_history(channel_id, "user", user_input)
            add_to_chat_history(channel_id, "model", reply_text)
            return reply_text
    except Exception as e:
        print(f"[Gemini 2.0 Fallback Error]: {e}")

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

            # Perbaikan: Mengirim 2 argumen (message.channel.id DAN clean_content)
            reply = await generate_ibuki_response(message.channel.id, clean_content)
            if reply:
                await message.reply(reply, mention_author=False)
            else:
                await message.reply("*melambaikan tangan imut* Ehehe~ Ibuki di sini! Ada apa Sensei panggil Ibuki? (*^-^*)", mention_author=False)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
