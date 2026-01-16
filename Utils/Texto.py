import unicodedata

def NormalizarTexto(Texto):
    """
    Transforma em Maiúsculo e remove acentos.
    Ex: 'São Paulo' -> 'SAO PAULO'
    """
    if not Texto:
        return ""
    
    # 1. Maiúsculo
    Texto = str(Texto).upper().strip()
    
    # 2. Remove Acentos (Decomposição NFD)
    # Separa 'á' em 'a' + '´', depois joga fora o '´'
    TextoNormalizado = ''.join(
        c for c in unicodedata.normalize('NFD', Texto)
        if unicodedata.category(c) != 'Mn'
    )
    
    return TextoNormalizado