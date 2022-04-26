import json


def gen_ladder(id):
    levels = []
    for j in range(100):
        exp = j * 100
        levels.append(dict(experience=exp))
    return dict(id=id, levels=levels)


def main():
    data = {}
    for ladder_type in ['weapon', 'artifact', 'hero']:
        key = f"{ladder_type}_ladder"
        data[key] = []
        data[key].append(gen_ladder("default_ladder"))
    with open('data/ladders.json', 'w') as j_f:
        json.dump(data, j_f, indent=2)


if __name__ == '__main__':
    main()

