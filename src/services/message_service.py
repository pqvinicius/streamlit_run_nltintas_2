import logging
from datetime import datetime, date
from typing import List, Optional, Dict
from src.gamificacao_vendedores import GamificacaoDB

logger = logging.getLogger(__name__)

class MessageService:
    def __init__(self, db: Optional[GamificacaoDB] = None):
        self.db = db or GamificacaoDB()

    def get_active_categories(self, ref_date: date) -> List[str]:
        """
        Retorna as categorias permitidas para o dia atual com base no calendário estratégico.
        Segunda -> PONTOS
        Quarta -> MENSAL
        Sexta -> SEMANAL
        Diárias (Manhã/Tarde) sempre inclusas.
        """
        weekday = ref_date.weekday()
        # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
        
        categories = []
        
        # Lógica de Horário para Diária
        hour = datetime.now().hour
        if hour < 13:
            categories.append("DIARIO_MANHA")
        else:
            categories.append("DIARIO_TARDE")

        # Regras de Dia da Semana
        if weekday == 0:  # Segunda
            categories.append("PONTOS")
        elif weekday == 2:  # Quarta
            categories.append("MENSAL")
        elif weekday == 4:  # Sexta
            categories.append("SEMANAL")
            
        return categories

    def get_randomized_message(self, categoria: str) -> Optional[str]:
        """
        Busca uma mensagem aleatória da categoria, respeitando a regra de anti-repetição.
        """
        res = self.db.get_random_template(categoria)
        if res:
            template_id, texto = res
            self.db.registrar_envio_template(categoria, template_id)
            logger.info(f"💬 [MENSAGEM] Selecionada para {categoria} (ID: {template_id})")
            return texto
        
        logger.warning(f"⚠️ [MENSAGEM] Nenhuma mensagem disponível para a categoria: {categoria}")
        return None

    def is_holiday(self, ref_date: date) -> bool:
        """Verifica se hoje é feriado."""
        return self.db.is_feriado(ref_date)

    def seed_initial_data(self):
        """Popula o banco com os templates fornecidos pelo usuário."""
        templates = [
            # DIARIO_MANHA (20)
            ("DIARIO_MANHA", "Bom dia, time! Que hoje seja um dia de foco, atitude e boas vendas."),
            ("DIARIO_MANHA", "Bom dia! Cada atendimento bem feito hoje constrói o resultado do mês."),
            ("DIARIO_MANHA", "Dia novo, oportunidade nova. Vamos pra cima!"),
            ("DIARIO_MANHA", "Bom dia! Comece o dia com atenção aos detalhes — eles fazem diferença."),
            ("DIARIO_MANHA", "Bora iniciar o dia com energia e meta na cabeça."),
            ("DIARIO_MANHA", "Bom dia, time! Organização cedo evita correria no fim do dia."),
            ("DIARIO_MANHA", "Hoje é mais uma chance de evoluir no ranking. Bom trabalho a todos!"),
            ("DIARIO_MANHA", "Bom dia! Quem começa forte, termina melhor."),
            ("DIARIO_MANHA", "Dia começando — foco no cliente e no resultado."),
            ("DIARIO_MANHA", "Bom dia, equipe! Pequenas vendas somam grandes resultados."),
            ("DIARIO_MANHA", "Atenção, foco e constância. Bom dia!"),
            ("DIARIO_MANHA", "Bom dia! Lembre-se: cada ponto começa em um bom atendimento."),
            ("DIARIO_MANHA", "Começando o dia com disciplina, o resultado vem."),
            ("DIARIO_MANHA", "Bom dia, time! Vamos fazer valer cada oportunidade hoje."),
            ("DIARIO_MANHA", "Dia novo, metas claras. Bora trabalhar!"),
            ("DIARIO_MANHA", "Bom dia! Venda é consequência de processo bem feito."),
            ("DIARIO_MANHA", "Comece o dia atento aos indicadores. Bom trabalho!"),
            ("DIARIO_MANHA", "Bom dia, equipe! Que hoje seja produtivo para todos."),
            ("DIARIO_MANHA", "Planejamento cedo, resultado garantido. Bom dia!"),
            ("DIARIO_MANHA", "Bom dia! O ranking começa a se mover desde a primeira venda."),
            
            # DIARIO_TARDE (20)
            ("DIARIO_TARDE", "Boa tarde, time! Ainda dá tempo de fazer diferença hoje."),
            ("DIARIO_TARDE", "Boa tarde! Últimas horas contam muito para o resultado."),
            ("DIARIO_TARDE", "Atenção ao fechamento — cada venda pesa no ranking."),
            ("DIARIO_TARDE", "Boa tarde, equipe! Foco até o último atendimento."),
            ("DIARIO_TARDE", "Ainda tem jogo! Bora buscar mais um resultado positivo."),
            ("DIARIO_TARDE", "Boa tarde! Ajuste o foco e siga firme."),
            ("DIARIO_TARDE", "Hora de acelerar e fechar bem o dia."),
            ("DIARIO_TARDE", "Boa tarde, time! Consistência agora evita retrabalho depois."),
            ("DIARIO_TARDE", "Último gás do dia — aproveitem as oportunidades."),
            ("DIARIO_TARDE", "Boa tarde! Venda bem feita agora vale ouro."),
            ("DIARIO_TARDE", "Atenção aos detalhes no fechamento. Boa tarde!"),
            ("DIARIO_TARDE", "O dia ainda não acabou. Bora somar pontos!"),
            ("DIARIO_TARDE", "Boa tarde, equipe! Persistência faz a diferença."),
            ("DIARIO_TARDE", "Últimas horas pedem atenção redobrada."),
            ("DIARIO_TARDE", "Boa tarde! Hora de transformar esforço em resultado."),
            ("DIARIO_TARDE", "Foco no cliente até o final do expediente."),
            ("DIARIO_TARDE", "Boa tarde! Cada venda agora impacta o ranking."),
            ("DIARIO_TARDE", "Ajuste fino e execução. Boa tarde!"),
            ("DIARIO_TARDE", "Hora de consolidar o dia com boas decisões."),
            ("DIARIO_TARDE", "Boa tarde, time! Vamos fechar bem."),
            
            # SEMANAL (20)
            ("SEMANAL", "Semana nova, metas novas. Bora começar forte!"),
            ("SEMANAL", "A semana começou — foco em constância e resultado."),
            ("SEMANAL", "Planejamento semanal bem feito gera resultado previsível."),
            ("SEMANAL", "Semana iniciando: atenção ao ranking e às metas."),
            ("SEMANAL", "Cada dia da semana importa. Vamos com foco."),
            ("SEMANAL", "Semana nova é chance de subir posições."),
            ("SEMANAL", "Olho nos indicadores desde o início da semana."),
            ("SEMANAL", "Comece a semana alinhando esforço e estratégia."),
            ("SEMANAL", "Constância ao longo da semana faz diferença no fim."),
            ("SEMANAL", "Semana aberta — bora construir um bom resultado."),
            ("SEMANAL", "Organização hoje evita pressão na sexta."),
            ("SEMANAL", "Semana nova, energia renovada."),
            ("SEMANAL", "Atenção aos detalhes desde o começo da semana."),
            ("SEMANAL", "Cada semana bem feita constrói o mês."),
            ("SEMANAL", "Semana começando — execute o básico bem feito."),
            ("SEMANAL", "Planeje, execute e acompanhe. Boa semana!"),
            ("SEMANAL", "Semana nova, foco no que traz resultado."),
            ("SEMANAL", "Bora manter o ritmo desde o primeiro dia."),
            ("SEMANAL", "Atenção ao ranking semanal — ele não perdoa distração."),
            ("SEMANAL", "Começo de semana é onde o jogo começa de verdade."),
            
            # MENSAL (20)
            ("MENSAL", "Novo mês, nova oportunidade de subir no ranking."),
            ("MENSAL", "Mês começando — foco total em meta e execução."),
            ("MENSAL", "Cada venda deste mês conta. Vamos com estratégia."),
            ("MENSAL", "O mês começou: organização agora evita correria depois."),
            ("MENSAL", "Mês novo, indicadores zerados. Bora construir resultado."),
            ("MENSAL", "Atenção ao planejamento mensal desde o início."),
            ("MENSAL", "O ranking mensal começa hoje."),
            ("MENSAL", "Mês novo pede disciplina e constância."),
            ("MENSAL", "Foco no processo para fechar o mês bem."),
            ("MENSAL", "Cada semana bem feita constrói um bom mês."),
            ("MENSAL", "Mês iniciado — execute com atenção aos detalhes."),
            ("MENSAL", "Planejamento mensal é diferencial competitivo."),
            ("MENSAL", "O mês começou, a meta também."),
            ("MENSAL", "Foco no cliente, o resultado vem no fechamento."),
            ("MENSAL", "Mês novo, energia renovada."),
            ("MENSAL", "Atenção aos pontos desde o primeiro dia do mês."),
            ("MENSAL", "Bora transformar esforço mensal em resultado concreto."),
            ("MENSAL", "Mês começando — consistência é chave."),
            ("MENSAL", "Olho no ranking mensal desde já."),
            ("MENSAL", "Um bom mês começa com boas decisões."),
            
            # PONTOS (20)
            ("PONTOS", "Parabéns pelos pontos conquistados! O ranking está se movimentando."),
            ("PONTOS", "Pontos somados — continue no ritmo!"),
            ("PONTOS", "Cada ponto reflete um bom atendimento."),
            ("PONTOS", "Seus pontos fazem diferença no ranking."),
            ("PONTOS", "Parabéns! A consistência está aparecendo nos pontos."),
            ("PONTOS", "Pontuação atualizada — foco para subir ainda mais."),
            ("PONTOS", "Cada ponto conta. Continue assim!"),
            ("PONTOS", "Bons resultados geram bons pontos."),
            ("PONTOS", "Ranking aquecido — seus pontos importam."),
            ("PONTOS", "Pontos acumulados com mérito."),
            ("PONTOS", "Continue focado, os pontos acompanham."),
            ("PONTOS", "Parabéns pela evolução na pontuação."),
            ("PONTOS", "Cada venda bem feita vira ponto no ranking."),
            ("PONTOS", "Seus pontos mostram disciplina e constância."),
            ("PONTOS", "Ranking atualizado — mantenha o ritmo."),
            ("PONTOS", "Bons atendimentos refletem diretamente nos pontos."),
            ("PONTOS", "Parabéns! Pontuação crescendo."),
            ("PONTOS", "Pontos conquistados com trabalho bem feito."),
            ("PONTOS", "Continue somando — o ranking responde rápido."),
            ("PONTOS", "Cada ponto é resultado de boas decisões."),
        ]
        
        self.db.seed_templates(templates)
        
        # Semeia feriados básicos (exemplo Nacional)
        feriados = [
            ("2025-01-01", "Confraternização Universal", "NACIONAL"),
            ("2025-04-21", "Tiradentes", "NACIONAL"),
            # Adicionar outros se necessário
        ]
        self.db.seed_feriados(feriados)

def get_message_service(db: Optional[GamificacaoDB] = None) -> MessageService:
    return MessageService(db)
