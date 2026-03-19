import os
import argparse
import subprocess
from pathlib import Path

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
except Exception as e:
    KaggleApi = None


def ensure_kaggle_config(kaggle_json_path: str | None):
    if kaggle_json_path:
        p = Path(kaggle_json_path).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"kaggle.json not found at {p}")
        # Use the directory as KAGGLE_CONFIG_DIR
        os.environ['KAGGLE_CONFIG_DIR'] = str(p.parent)
        # Ensure file is named kaggle.json
        if p.name != 'kaggle.json':
            raise ValueError('El archivo debe llamarse kaggle.json')


def download_dataset(dataset_slug: str, dest: str, unzip: bool):
    api = KaggleApi()
    api.authenticate()
    print(f"Descargando dataset {dataset_slug} -> {dest} (unzip={unzip})")
    api.dataset_download_files(dataset_slug, path=dest, unzip=unzip, quiet=False)


def pull_kernel(kernel_slug: str, dest: str):
    api = KaggleApi()
    api.authenticate()
    print(f"Pull kernel {kernel_slug} -> {dest}")
    api.kernels_pull(kernel_slug, path=dest)


def call_import(data_dir: str, mongo_uri: str, db: str, include: str | None):
    cmd = ['python', 'load_worldcup_to_mongo.py', '--data-dir', data_dir, '--mongo-uri', mongo_uri, '--db', db]
    if include:
        cmd += ['--include', include]
    print('Ejecutando import:',' '.join(cmd))
    subprocess.check_call(cmd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Descarga datasets o kernels de Kaggle y opcionalmente ejecuta import a MongoDB')
    parser.add_argument('--dataset', help='Slug del dataset en Kaggle, ej: rishi0588/fifa-world-cup-dataset')
    parser.add_argument('--kernel', help='Slug del kernel en Kaggle si prefieres descargar el notebook')
    parser.add_argument('--data-dir', default='data', help='Directorio destino')
    parser.add_argument('--unzip', action='store_true', help='Descomprimir archivos zip descargados')
    parser.add_argument('--kaggle-json', help='Ruta a tu kaggle.json (opcional). Si no se proporciona, se usará la configuración por defecto (~/.kaggle/kaggle.json)')
    parser.add_argument('--call-import', action='store_true', help='Llamar a load_worldcup_to_mongo.py automáticamente después de descargar')
    parser.add_argument('--mongo-uri', default='mongodb://localhost:27017', help='URI para pasar al import si se usa --call-import')
    parser.add_argument('--db', default='worldcup', help='DB name para pasar al import si se usa --call-import')
    parser.add_argument('--include', help='Lista separada por comas de colecciones a incluir cuando se llame al import')
    args = parser.parse_args()

    if KaggleApi is None:
        raise RuntimeError('kaggle package no está instalado. Ejecuta: pip install kaggle')

    Path(args.data_dir).mkdir(parents=True, exist_ok=True)

    ensure_kaggle_config(args.kaggle_json)

    if args.dataset:
        download_dataset(args.dataset, args.data_dir, args.unzip)

    if args.kernel:
        pull_kernel(args.kernel, args.data_dir)

    if args.call_import:
        call_import(args.data_dir, args.mongo_uri, args.db, args.include)

    print('Operación completada.')
