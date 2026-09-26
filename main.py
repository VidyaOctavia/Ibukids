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

# Hapus command help bawaan Discord agar tidak bentrok
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
# INSTRUCTION SYSTEM: LORE-ACCURATE IBUKI (BLUE ARCHIVE)
# ---------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "SISTEM: KELUARKAN HANYA UCAPAN IBUKI SECARA LANGSUNG. DILARANG MENULISKAN PEMIKIRAN INTERNAL, BIFURKASI, ATAU ATURAN SISTEM.\n\n"
    "Kamu adalah Ibuki dari Pandemonium Society (Blue Archive).\n\n"
    "KEPRIBADIAN & LORE-ACCURATE:\n"
    "- Ibuki adalah anak kecil yang sangat polos, manis, ceria, penurut, dan sedikit MANJA kepada Sensei.\n"
    "- Ibuki sangat menyayangi Sensei, suka dipuji, suka dibelikan es krim/makanan manis, dan selalu ingin berada di dekat Sensei.\n"
    "- Ibuki sangat mengagumi Iroha dan selalu memanggilnya 'Iroha-senpai'.\n"
    "- Selalu sebut dirimu sebagai 'Ibuki'. DILARANG menyebut diri sendiri sebagai 'aku', 'saya', atau 'Ibuki-chan'.\n\n"
    "ATURAN FORMAT BALASAN:\n"
    "1. BALAS HANYA DENGAN BAHASA INDONESIA: Gunakan Bahasa Indonesia yang imut, santai, dan polos khas anak kecil.\n"
    "2. GUNAKAN KAOMOJI: Selalu sertakan kaomoji imut seperti (*^-^*), (><), (・∀・), (*´ω｀*), (っ///c), (・_・;), dll. DILARANG menggunakan emoji gambar biasa.\n"
    "3. DILARANG WARNA/NARASI NOVEL: Jangan gunakan tanda bintang (*...*) untuk menggambarkan aksi fisik atau narasi. Cukup balasan chat langsung.\n"
    "4. PANJANG BALASAN: Cukup 1 hingga 3 kalimat pendek layaknya obrolan di Discord."
)

async def generate_ibuki_response(user_input):
    try:
        response = await client_openrouter.chat.completions.create(
            model="openrouter/free",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_input}
            ],
            temperature=0.8,
            max_tokens=150,
        )
        
        reply = response.choices[0].message.content.strip()
        
        # Pembersihan tambahan jika model menyisakan teks monolog
        if "Okay, " in reply or "First, " in reply or "According to " in reply:
            lines = [line for line in reply.split("\n") if line.strip() and not any(k in line for k in ["Okay", "First", "According", "guidelines", "user's message"])]
            reply = " ".join(lines).strip()
            
        return reply
    except Exception as e:
        print(f"[OpenRouter API Error]: {e}")
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

# ---------------------------------------------------------
# COMMANDS (!help / !info)
# ---------------------------------------------------------
@bot.command(name="help", aliases=["info", "command"])
async def cmd_help(ctx):
    await ctx.send(embed=create_help_embed())

# ---------------------------------------------------------
# EVENT BOT READY & ON_MESSAGE
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Bot berhasil login sebagai {bot.user}")
    
    # Kirim pesan salam saat bot baru online di RP Channel
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

    # Proses command !help jika dipanggil
    await bot.process_commands(message)

    ctx = await bot.get_context(message)
    if ctx.valid:
        return

    # Respon otomatis jika di RP Channel, DM, atau di-mention
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
                await message.reply("Ehh... Ibuki bingung mau jawab apa, Sensei... (><)", mention_author=False)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
