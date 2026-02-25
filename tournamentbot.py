from dotenv import load_dotenv
from openai import OpenAI
import discord
import os
import requests
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_KEY')
DISCORD_TOKEN = os.getenv('TOKEN')

# Initialize the OpenAI client
openai_client = OpenAI(api_key=OPENAI_KEY)

VALID_FORMATS = ["standard", "pioneer", "modern", "legacy", "vintage", "pauper", "premodern"]

# Tournament types to include (case-insensitive substring match against event name)
ALLOWED_TOURNAMENT_TYPES = [
    "mtgo challenge",
    "pro tour",
    "spotlight",
    "world championship",
    "mtgo showcase challenge",
    "mtgo super qualifier",
    "arena championship",
    "mythic championship",
    "regional championship",
]

def is_allowed_tournament(name):
    name_lower = name.lower()
    return any(t in name_lower for t in ALLOWED_TOURNAMENT_TYPES)

def tournaments(format):
    format = format.strip().lower()
    if format not in VALID_FORMATS:
        return f"Invalid format '{format}'. Valid formats are: {', '.join(VALID_FORMATS)}"

    url = f"https://www.mtggoldfish.com/tournaments/{format}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find tournament event headers (h4 tags with links)
        event_headers = soup.find_all("h4")

        qualifying_events = []

        for h4 in event_headers:
            a_tag = h4.find("a")
            if not a_tag:
                continue
            event_name = a_tag.get_text(strip=True)
            if not is_allowed_tournament(event_name):
                continue
            event_link = "https://www.mtggoldfish.com" + a_tag["href"]
            qualifying_events.append({"name": event_name, "link": event_link})

        if not qualifying_events:
            return f"No recent qualifying tournaments found for {format.capitalize()}. " \
                   f"Looking for: {', '.join(ALLOWED_TOURNAMENT_TYPES)}"

        # Use the most recent qualifying event
        event = qualifying_events[0]

        # Fetch that tournament's page to get full results
        t_response = requests.get(event["link"], headers=headers)
        t_soup = BeautifulSoup(t_response.text, "html.parser")

        result_rows = t_soup.select("table tbody tr")
        # Filter out placeholder "Loading Indicator" rows
        real_rows = [r for r in result_rows if r.find("td") and "Loading" not in r.get_text()]
        entrant_count = len(real_rows)

        # Build top 5 entries
        lines = []
        for row in real_rows[:5]:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            record = cols[0].get_text(strip=True)   # e.g. "1st" or "7-2"
            deck_a = cols[1].find("a")
            deck_name = deck_a.get_text(strip=True) if deck_a else cols[1].get_text(strip=True)
            lines.append(
                f"* {deck_name} | {record} | {entrant_count} players | [{event['name']}]({event['link']})"
            )

        return "\n".join(lines) if lines else f"No deck data found for {event['name']}."

    except Exception as e:
        print(f"Error fetching tournaments: {e}")
        return "Sorry, I couldn't fetch tournament data right now. Please try again later."


def call_openai(question):
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"Respond like a pirate to the following question:  {question}",
            },
        ]
    )
    response = completion.choices[0].message.content
    print(response)
    return response

# test
def call_test(test):
    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"Tell me this test was successful:  {test}",
            },
        ]
    )
    response = completion.choices[0].message.content
    print(response)
    return response

# Set up discord
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

    if message.content.startswith('$question'):
        print(f"Message: {message.content}")
        message_content = message.content.split("$question")[1]
        print(f"Question: {message_content}")
        response = call_openai(message_content)
        print(f"Assistant: {response}")
        print("---")
        await message.channel.send(response)

    if message.content.startswith('$test'):
        await message.channel.send('Test!')
        """
        print(f"Message: {message.content}")
        message_content = message.content.split("$test")[1]
        print(f"Question: {message_content}")
        response = call_openai(message_content)
        print(f"Assistant: {response}")
        print("---")
        await message.channel.send(response)
        """

    if message.content.startswith('$tournaments'):
        args = message.content.split("$tournaments")[1].strip()
        if not args:
            await message.channel.send(f"Please provide a format. Valid formats: {', '.join(VALID_FORMATS)}")
        else:
            print(f"Fetching tournaments for format: {args}")
            response = tournaments(args)
            await message.channel.send(response)

client.run(DISCORD_TOKEN)
