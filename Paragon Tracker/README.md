# Diablo 4 Paragon 300 XP Tracker

Medidor de XP pessoal: uma barra grande com o progresso **total até o Paragon 300**, mais uma barra
do nível atual. Tudo local, sem internet. Toda a curva de XP vem da planilha
`D4 LoH Paragon XP Current S13.xlsx` (lida na inicialização; nada de XP fixo no código).

## Estrutura

```
Diablo4ParagonTracker/
├── main.py                 # interface (Tkinter)
├── paragon_core.py         # leitura da planilha + cálculos (inteiros) + formatação pt-BR
├── test_paragon.py         # testes automáticos
├── D4 LoH Paragon XP Current S13.xlsx
├── requirements.txt
├── build.bat               # gera o .exe (Windows)
└── progress.json           # criado automaticamente ao usar
```

## Executar

Requer Python 3.9+ (Tkinter já vem com o Python do Windows/macOS; no Linux: `sudo apt install python3-tk`).

```bash
pip install -r requirements.txt
python main.py
```

## Como usar

* **Método B (XP total):** digite o XP acumulado (com ou sem pontos) e o programa calcula o Paragon,
  o XP dentro do nível, os restantes e as duas barras.
* **Método A (nível + XP no nível):** informe o Paragon atual e o XP dentro dele.
* Os dois métodos ficam sempre sincronizados: editar um preenche o outro na hora.
  Enter, o botão **ATUALIZAR** ou sair do campo normalizam a formatação.
* O último XP é salvo em `progress.json` (ao lado do programa) e recarregado na próxima abertura.
* Valores inválidos mostram mensagem; valores fora dos limites são corrigidos (ex.: XP acima do
  máximo é limitado a P300 com aviso).

## Como a planilha é interpretada

Aba `Instructions`, tabela em A1:D301 (cabeçalho na linha 1). O programa procura por cabeçalhos,
não por posições fixas: **Level** e **XP Required** (e, opcionalmente, **Cumulative XP** para
conferência), em qualquer aba. Para trocar a curva, basta substituir o .xlsx mantendo esses cabeçalhos
e níveis sequenciais a partir de 1 (as células precisam ter valor salvo, não só fórmula).

* `XP Required` do nível L = XP para ir de P(L-1) até P(L).
* XP acumulado do P(L) = soma de `XP Required` de 1 até L. Total (P300) = 58.237.517.372 na S13.
* XP total X => Paragon = maior L com acumulado(L) <= X. Tamanho do nível L = `XP Required` de L+1.
* **Paragon 0** = menos de 600.000 XP (ainda não alcançou o P1); o total de 58.237.517.372 inclui esse
  primeiro trecho.

## Testes

```bash
python -m unittest -v test_paragon
```

Cobrem P1/100/200/250/279/280/290/299/300, 0 XP, limites exatos de todos os 300 níveis, XP acima do
máximo, negativos/texto, 20.000 ida-e-volta aleatórias e soma independente da planilha.

## Gerar o .exe (Windows, sem precisar de Python para rodar)

```bat
build.bat
```

ou manualmente:

```bat
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --windowed --name Diablo4ParagonTracker main.py
```

O resultado fica em `dist\Diablo4ParagonTracker.exe`. **Copie a planilha .xlsx para a mesma pasta do
.exe**: assim você pode trocar a planilha sem recompilar, e o `progress.json` também é salvo ali.
(Opcional: embutir uma cópia de reserva com
`--add-data "D4 LoH Paragon XP Current S13.xlsx;."`; a planilha ao lado do .exe tem prioridade.)
O .exe precisa ser gerado no Windows; o PyInstaller não faz compilação cruzada.
