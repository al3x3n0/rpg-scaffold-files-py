import argparse
import os
from pathlib import Path

from acrpg.codegen.csharp import CodeGenCSharp
from acrpg.codegen.sol import SolCodeGenGo
from acrpg.model.data import GameData


ROOT_DIR = Path(__file__).parent.resolve()
DATA_DIR = ROOT_DIR.joinpath('data')


def load_all_data():
    gd = GameData()
    for root, dirnames, filenames in os.walk(str(DATA_DIR)):
        for filename in filenames:
            fpath = Path(root).joinpath(Path(filename))
            if fpath.suffix == '.json':
                gd.merge(GameData.parse_file(fpath))
    return gd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", type=str, default='AlienCell')
    parser.add_argument("--out-dir", type=str, default=str(ROOT_DIR.joinpath("generated")))
    parser.add_argument("--server-out-dir", type=str, default=ROOT_DIR.joinpath("gen_server"))
    parser.add_argument("--console-app-out-dir", type=str, default=ROOT_DIR.joinpath("gen_console_app"))
    args = parser.parse_args()

    gen_dir = Path(args.out_dir)
    #sol_path = ROOT_DIR.joinpath("contracts/generated")
    #
    game_data = load_all_data()
    csharp_gen = CodeGenCSharp(args.project_name, gen_dir, game_data,
                               server_out_dir=Path(args.server_out_dir),
                               console_app_out_dir=Path(args.console_app_out_dir))
    #sol_gen = SolCodeGenGo('AlienCell', sol_path, game_data)
    #
    csharp_gen.generate()
    #sol_gen.generate()


if __name__ == '__main__':
    main()
