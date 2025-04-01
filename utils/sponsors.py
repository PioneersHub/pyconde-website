import json


def json_to_lektor(sponsor):
    pass


def load_sponsors():
    sponsors = []
    with open("databags/sponsors.json") as f:
        j = json.load(f)
        sponsors = j["types"]
    return sponsors


def main():
    sponsors = load_sponsors()
    print(sponsors)


if __name__ == "__main__":
    main()
