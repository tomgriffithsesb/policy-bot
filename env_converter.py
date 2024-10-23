import json

# Read the JSON file with UTF-8 encoding
with open('env.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# Open the output text file

with open('env.txt', 'w', encoding='utf-8') as file:
    for item in data:
        file.write(f'{item["name"]}={item["value"]}\n')