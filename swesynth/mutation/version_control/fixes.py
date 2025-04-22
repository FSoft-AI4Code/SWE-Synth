"""
> cd pylint-dev_astroid
> find . -type f -name "test2function_mapping.json.zst" | while read -r file; do
  length=$(zstdcat "$file" | jq '.function_to_test_mapping | length');
  if [ "$length" -eq 0 ]; then
    echo "$file: $length";
  fi;
done

./2.13/fe058bff95745371df5796286d33677c21137847/original/test2function_mapping.json.zst: 0
./2.14/0c9ab0fe56703fa83c73e514a1020d398d23fa7f/original/test2function_mapping.json.zst: 0
./2.14/49691cc04f2d38b174787280f7ed38f818c828bd/original/test2function_mapping.json.zst: 0
./2.15/2108ae51b516458243c249cf67301cb387e33afa/original/test2function_mapping.json.zst: 0
./2.15/29b42e5e9745b172d5980511d14efeac745a5a82/original/test2function_mapping.json.zst: 0
./2.15/56a65daf1ba391cc85d1a32a8802cfd0c7b7b2ab/original/test2function_mapping.json.zst: 0
./2.15/bcaecce5634a30313e574deae101ee017ffeff17/original/test2function_mapping.json.zst: 0
./3.0/1113d490ec4a94cdc1b35f45abfdaca9f19fa31e/original/test2function_mapping.json.zst: 0
./3.0/514991036806e9cda2b12cef8ab3184ac373bd6c/original/test2function_mapping.json.zst: 0
./3.0/efb34f2b84c9f019ffceacef3448d8351563b6a2/original/test2function_mapping.json.zst: 0
"""

PYLINT_DEV_ASTROID_CORRUPTED_COMMITS: set[str] = {
    "fe058bff95745371df5796286d33677c21137847",
    "0c9ab0fe56703fa83c73e514a1020d398d23fa7f",
    "49691cc04f2d38b174787280f7ed38f818c828bd",
    "2108ae51b516458243c249cf67301cb387e33afa",
    "29b42e5e9745b172d5980511d14efeac745a5a82",
    "56a65daf1ba391cc85d1a32a8802cfd0c7b7b2ab",
    "bcaecce5634a30313e574deae101ee017ffeff17",
    "1113d490ec4a94cdc1b35f45abfdaca9f19fa31e",
    "514991036806e9cda2b12cef8ab3184ac373bd6c",
    "efb34f2b84c9f019ffceacef3448d8351563b6a2",
}

ASTROPY_CORRUPTED_COMMITS: set[str] = {"4fc9f31af6c5659c3a59b66a387894c12203c946", "d5bd3f68bb6d5ce3a61bdce9883ee750d1afade5"}

# --- post remove commits ---
MONAI_CORRUPTED_COMMITS: set[str] = {
    "2c5c89f86ee718b31ce2397c699cd67a8c78623f",
    "5a644e4edcc37e5c963e52fda6fab4c85b3ff02e",
}

DASK_CORRUPTED_COMMITS: set[str] = {
    "0bc155eca6182eb0ee9bd3d671321e90235d17e5",
    "898afc04208aba91dc52acb5e04cc7a76f9c1013",
}

PYDANTIC_CORRUPTED_COMMITS: set[str] = {
    "5fc166c031dc3665748c5ce6c0284abd5e61c195",
}

CORRUPTED_COMMITS: dict[str, set[str]] = {
    "project-monai/monai": MONAI_CORRUPTED_COMMITS,
    "dask/dask": DASK_CORRUPTED_COMMITS,
    "pydantic/pydantic": PYDANTIC_CORRUPTED_COMMITS,
}
