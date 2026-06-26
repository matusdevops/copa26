import streamlit as st
import json
import os
import random
import io
import base64
import time

from groq import Groq
from PIL import Image, ImageFilter

# =====================================================
# CONFIGURAÇÃO
# =====================================================

st.set_page_config(
    page_title="Jogo das Dicas",
    layout="wide"
)

# ================== GROQ API KEY ==================
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

IMAGES_FOLDER = "imagens"
VALORES_BLUR = [40, 20, 10, 5]
NUM_DICAS = 3

# Tamanho final padrão para TODAS as imagens (largura, altura)
TAMANHO_PADRAO = (900, 700)

# =====================================================
# VERIFICAÇÕES
# =====================================================

if not os.path.exists(IMAGES_FOLDER):
    st.error("Pasta 'imagens' não encontrada.")
    st.stop()

imagens = [
    os.path.join(IMAGES_FOLDER, arquivo)
    for arquivo in os.listdir(IMAGES_FOLDER)
    if arquivo.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
]

if not imagens:
    st.error("Nenhuma imagem encontrada na pasta.")
    st.stop()

# =====================================================
# SESSION STATE
# =====================================================

for chave, valor in {
    "jogo_iniciado": False,
    "imagens_usadas": [],
    "imagem_atual": None,
    "dicas": None,
    "resposta_correta": "",
    "indice_dica": 0,
    "blur_atual": VALORES_BLUR[0],
    "acertou": False,
    "revelada": False,
    "botao_jogar_novamente": False,
    "tentativas": 0,
}.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor

# =====================================================
# FUNÇÕES
# =====================================================

def normalizar(texto):
    return texto.lower().replace("_", " ").replace("-", " ").strip()


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def gerar_dicas(caminho_imagem: str, nome_arquivo: str):
    """Gera dicas usando Groq + Llama 4 Scout (melhor modelo de visão atual)"""
    prompt = f"""
Analise com muita atenção a imagem e crie **exatamente 3 dicas progressivas** específicas sobre o que aparece nela, focando na pessoa (se é um ator, cantor, instrumentista, jogador,...), paisagem (de qual país?) ou gastronomia(cultura brasileira ou estrangeira).

- Dica 1: Difícil / sutil
- Dica 2: Nível médio
- Dica 3: Fácil (bem reveladora, mas sem dizer o nome direto)

Regras:
- Seja específico sobre objetos, cores, formas, cenário, detalhes visíveis, etc.
- As dicas devem ser baseadas **apenas** no conteúdo visual da imagem.
- Nunca revele o nome exato do objeto principal.
- Não use dicas genéricas.
- Responda APENAS com JSON válido.

Formato:
{{
  "dica1": "...",
  "dica2": "...",
  "dica3": "..."
}}
"""

    for tentativa in range(3):
        try:
            base64_image = encode_image(caminho_imagem)

            resposta = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=600,
                temperature=0.7
            )

            conteudo = resposta.choices[0].message.content.strip()
            return json.loads(conteudo)

        except Exception as e:
            print(f"Tentativa {tentativa+1} falhou: {e}")
            if tentativa < 2:
                time.sleep(2)

    st.error("❌ Erro ao gerar dicas. Verifique sua chave Groq ou limite de uso.")
    return {
        "dica1": "Não foi possível analisar a imagem no momento.",
        "dica2": "Tente recarregar a página.",
        "dica3": "Verifique sua conexão com a internet."
    }


def redimensionar_com_crop(img: Image.Image, tamanho: tuple) -> Image.Image:
    """
    Redimensiona a imagem para preencher exatamente `tamanho`,
    cortando o excesso (crop centralizado) para não distorcer a proporção.
    """
    largura_alvo, altura_alvo = tamanho
    proporcao_alvo = largura_alvo / altura_alvo

    largura_orig, altura_orig = img.size
    proporcao_orig = largura_orig / altura_orig

    if proporcao_orig > proporcao_alvo:
        # Imagem original é mais "larga" que o alvo -> ajusta pela altura e corta as laterais
        nova_altura = altura_alvo
        nova_largura = int(nova_altura * proporcao_orig)
    else:
        # Imagem original é mais "alta" que o alvo -> ajusta pela largura e corta topo/base
        nova_largura = largura_alvo
        nova_altura = int(nova_largura / proporcao_orig)

    img_redimensionada = img.resize((nova_largura, nova_altura), Image.LANCZOS)

    # Crop centralizado para o tamanho exato
    left = (nova_largura - largura_alvo) / 2
    top = (nova_altura - altura_alvo) / 2
    right = left + largura_alvo
    bottom = top + altura_alvo

    return img_redimensionada.crop((left, top, right, bottom))


def aplicar_desfoque(caminho, blur):
    img = Image.open(caminho).convert("RGB")
    img = redimensionar_com_crop(img, TAMANHO_PADRAO)

    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def escolher_nova_imagem():
    restantes = [img for img in imagens if img not in st.session_state.imagens_usadas]
    if not restantes:
        st.session_state.imagens_usadas = []
        restantes = imagens.copy()

    escolha = random.choice(restantes)

    st.session_state.imagem_atual = escolha
    st.session_state.imagens_usadas.append(escolha)

    st.session_state.indice_dica = 0
    st.session_state.blur_atual = VALORES_BLUR[0]
    st.session_state.acertou = False
    st.session_state.revelada = False
    st.session_state.tentativas = 0

    nome_resposta = os.path.splitext(os.path.basename(escolha))[0]
    st.session_state.resposta_correta = nome_resposta

    with st.spinner("🔍 Analisando a imagem com Llama 4 Scout..."):
        st.session_state.dicas = gerar_dicas(escolha, os.path.basename(escolha))


# =====================================================
# INTERFACE
# =====================================================

if st.session_state.botao_jogar_novamente:
    st.session_state.botao_jogar_novamente = False
    escolher_nova_imagem()

if not st.session_state.jogo_iniciado:
    st.title("🎯 Jogo das Dicas")
    st.write("A IA analisa **visualmente** cada imagem para gerar dicas personalizadas.")
    if st.button("Iniciar Jogo", use_container_width=True):
        st.session_state.jogo_iniciado = True
        escolher_nova_imagem()
        st.rerun()
    st.stop()

# Jogo
blur = 0 if st.session_state.acertou or st.session_state.revelada else st.session_state.blur_atual
imagem = aplicar_desfoque(st.session_state.imagem_atual, blur)

col_img, col_lateral = st.columns([2, 1])

with col_img:
    st.image(imagem, width=TAMANHO_PADRAO[0])

with col_lateral:
    st.subheader("💡 Dicas")

    if st.session_state.dicas:
        for i in range(st.session_state.indice_dica):
            dica = st.session_state.dicas.get(f"dica{i+1}", "")
            if dica:
                st.markdown(f"- {dica}")

    if not st.session_state.acertou and not st.session_state.revelada:
        if st.button("Pedir Dica"):
            if st.session_state.indice_dica < NUM_DICAS:
                st.session_state.indice_dica += 1
                st.session_state.blur_atual = VALORES_BLUR[st.session_state.indice_dica]
                st.rerun()
            else:
                st.warning("Não há mais dicas disponíveis.")

    if not st.session_state.acertou and not st.session_state.revelada:
        with st.form("form_resposta"):
            palpite = st.text_input("Digite sua resposta:")
            enviar = st.form_submit_button("Enviar")
            if enviar and palpite.strip():
                if normalizar(palpite) == normalizar(st.session_state.resposta_correta):
                    st.session_state.acertou = True
                    st.rerun()
                else:
                    st.session_state.tentativas += 1
                    if st.session_state.tentativas >= 4:
                        st.session_state.revelada = True
                        st.rerun()
                    else:
                        st.error(f"Incorreto. Tentativas restantes: {4 - st.session_state.tentativas}")

# Resultados
if st.session_state.acertou:
    st.success("🎉 Parabéns! Você acertou!")
    st.balloons()
    if st.button("Jogar Novamente", use_container_width=True):
        st.session_state.botao_jogar_novamente = True
        st.rerun()

elif st.session_state.revelada:
    st.error("❌ Você não acertou.")
    st.info(f"**Resposta correta:** {normalizar(st.session_state.resposta_correta).title()}")
    if st.button("Jogar Novamente", use_container_width=True):
        st.session_state.botao_jogar_novamente = True
        st.rerun()

else:
    if st.button("Pular Imagem", use_container_width=True):
        st.session_state.botao_jogar_novamente = True
        st.rerun()
