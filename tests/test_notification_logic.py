from datetime import datetime
from src.services.notification_policy import NotificationPolicy
from pathlib import Path
import json
import shutil

def test_simulation():
    test_history = Path("data/test_notification_history.json")
    if test_history.exists(): test_history.unlink()
    
    policy = NotificationPolicy(history_file=test_history)
    
    print("--- Teste 1: Janelas Diárias ---")
    d1 = datetime(2025, 1, 8, 11, 0) # Quarta, 11h
    shift = policy.deve_enviar_ranking_diario(d1)
    print(f"11h: Deve enviar? {shift}") # Esperado: M
    if shift: policy.registrar_envio_diario(d1, shift)
    
    shift_retry = policy.deve_enviar_ranking_diario(d1)
    print(f"11h (repetido): Deve enviar? {shift_retry}") # Esperado: None
    
    d2 = datetime(2025, 1, 8, 17, 0) # Quarta, 17h
    shift2 = policy.deve_enviar_ranking_diario(d2)
    print(f"17h: Deve enviar? {shift2}") # Esperado: T
    
    print("\n--- Teste 2: Regras Semanais ---")
    segunda = datetime(2025, 1, 6, 10, 0)
    quarta = datetime(2025, 1, 8, 10, 0)
    sexta = datetime(2025, 1, 10, 10, 0)
    
    print(f"Segunda (Pontos): {policy.deve_enviar_ranking_pontos(segunda)}")
    print(f"Quarta (Mensal): {policy.deve_enviar_ranking_mensal(quarta)}")
    print(f"Sexta (Semanal): {policy.deve_enviar_ranking_semanal(sexta)}")
    
    print("\n--- Teste 3: Evolução Individual ---")
    vendedor = "TestBot"
    t1 = ["Bronze"]
    should1 = policy.deve_enviar_mensagem_individual(vendedor, quarta, t1)
    print(f"Ganhou Bronze: {should1}") # True
    if should1: policy.registrar_envio_individual(vendedor, quarta, t1)
    
    should2 = policy.deve_enviar_mensagem_individual(vendedor, quarta, t1)
    print(f"Bronze de novo (mesmo dia): {should2}") # False
    
    t2 = ["Bronze", "Prata"]
    should3 = policy.deve_enviar_mensagem_individual(vendedor, quarta, t2)
    print(f"Evoluiu para Prata: {should3}") # True
    if should3: policy.registrar_envio_individual(vendedor, quarta, t2)
    
    print("\n--- Mensagem Gerada ---")
    print(policy.gerar_mensagem_conquista(vendedor, t2, 1500))

    # Limpeza
    # if test_history.exists(): test_history.unlink()

if __name__ == "__main__":
    test_simulation()
