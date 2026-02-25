from dotenv import load_dotenv
from openai import OpenAI
import discord
import os
import requests
import re
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()
OPENAI_KEY = os.getenv('OPENAI_KEY')
DISCORD_TOKEN = os.getenv('TOKEN')

# Initialize the OpenAI client
openai_client = OpenAI(api_key=OPENAI_KEY)

VALID_FORMATS = ["standard", "pioneer", "modern", "legacy", "vintage", "pauper", "premodern"]

# TODO: Re-enable filtering once basic scraping is confirmed working.
# Filter tournaments to only these event types:
# ALLOWED_TOURNAMENT_TYPES = [
#     "challenge",
#     "pro tour",
#     "spotlight",
#     "world championship",
#     "showcase challenge",
#     "super qualifier",
#     "arena championship",
#     "mythic championship",
#     "regional championship",
# ]
# def is_allowed_tournament(name):
#     name_lower = name.lower()
#     return any(t in name_lower for t in ALLOWED_TOURNAMENT_TYPES)

def get_decklist_count(table):
    """
    After each tournament table, MTGGoldfish renders a <p> tag like 'View All 32 Decks'.
    If that tag is absent, the table shows all decks (count = number of rows).
    Returns an int.
    """
    p = table.find_next_sibling("p")
    if p:
        match = re.search(r"View All (\d+) Decks", p.get_text())
        if match:
            return int(match.group(1))
    # No "View All" tag — all decks are shown in the table
    return len([r for r in table.find_all("tr") if r.find("td")])

def tournaments(format_name):
    format_name = format_name.strip().lower()
    if format_name not in VALID_FORMATS:
        return f"Invalid format '{format_name}'. Valid formats are: {', '.join(VALID_FORMATS)}"

    print(f"Fetching recent {format_name} tournaments...")

    url = f"https://www.mtggoldfish.com/tournaments/{format_name}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Page status: {resp.status_code}")

        soup = BeautifulSoup(resp.text, "html.parser")
        h4s = soup.find_all("h4")
        print(f"Tournament headers found: {len(h4s)}")

        results = []
        for h4 in h4s:
            a = h4.find("a")
            if not a:
                continue

            event_name = a.get_text(strip=True)
            event_link = "https://www.mtggoldfish.com" + a["href"]

            table = h4.find_next_sibling("table")
            if not table:
                continue

            # Filter: only tournaments with 32+ decks
            decklist_count = get_decklist_count(table)
            if decklist_count < 32:
                print(f"  Skipping '{event_name}' ({decklist_count} decks)")
                continue

            # TODO: Uncomment to also filter by tournament type:
            # if not is_allowed_tournament(event_name):
            #     continue

            rows = [r for r in table.find_all("tr") if r.find("td")]
            if not rows:
                continue

            cols = rows[0].find_all("td")
            record    = cols[0].get_text(strip=True)
            deck_a    = cols[1].find("a")
            deck_name = deck_a.get_text(strip=True) if deck_a else cols[1].get_text(strip=True)

            print(f"  Adding '{event_name}' ({decklist_count} decks)")
            results.append(f"* {deck_name} | {record} | {decklist_count} players | [{event_name}]({event_link})")

            if len(results) >= 3:
                break

        if not results:
            return f"No tournaments with 32+ decks found for {format_name.capitalize()}."

        return "\n".join(results)

    except Exception as e:
        print(f"Error: {e}")
        return "Sorry, couldn't fetch tournament data right now. Please try again later."


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