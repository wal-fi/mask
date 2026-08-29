# Masking Engine Skill

Mantenha separados:
- matching
- exceptions
- transformation

Pipeline:
Column → Exception Matcher → Masking Matcher → Transformer → Result

Não coloque lógica específica de CPF dentro do core.

Preserve NULL.

Transformers devem ser plugáveis e testáveis isoladamente.
