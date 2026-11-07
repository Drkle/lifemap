"""Regresión del entorno inmutable que ignoraba la activación manual de E2."""
import re
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('nombre',['EJECUTAR_ENTREGA2','MODELO_PATH','MANIFEST_PATH'])
def test_variables_dinamicas_no_se_fijan_en_environment_declarativo(nombre):
    texto=(ROOT/'Jenkinsfile').read_text()
    entorno=re.search(r'\n    environment \{(.*?)\n    \}',texto,re.S).group(1)
    assert not re.search(r'^\s*'+nombre+r'\s*=',entorno,re.M), 'Declarative impediría el cambio imperativo'
    assert f'env.{nombre} = seleccionado.' in texto
