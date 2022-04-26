import os
from pathlib import Path

from acrpg.codegen.csharp import CodeGenCSharp
from acrpg.codegen.sol import SolCodeGenGo
from acrpg.model.data import GameData


ROOT_DIR = Path(__file__).parent.resolve()
DATA_DIR = ROOT_DIR.joinpath('data')
GEN_DIR = ROOT_DIR.joinpath("generated")


def load_all_data():
    gd = GameData()
    for root, dirnames, filenames in os.walk(str(DATA_DIR)):
        for filename in filenames:
            fpath = Path(root).joinpath(Path(filename))
            if fpath.suffix == '.json':
                gd.merge(GameData.parse_file(fpath))
    return gd


def main():
    csharp_path = GEN_DIR.joinpath("csharp")
    sol_path = ROOT_DIR.joinpath("contracts/generated")
    #
    game_data = load_all_data()
    csharp_gen = CodeGenCSharp(csharp_path, game_data)
    sol_gen = SolCodeGenGo(sol_path, game_data)
    #
    #csharp_gen.generate()
    sol_gen.generate()


if __name__ == '__main__':
    main()
