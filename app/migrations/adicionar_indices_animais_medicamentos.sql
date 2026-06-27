-- Adiciona índices nos campos mais filtrados do sistema, que ficaram sem
-- índice desde a criação da tabela. Mudar o modelo em animal.py/medicamento.py
-- não altera uma tabela que já existe — essa migração é o que de fato cria
-- os índices no banco já em uso.
--
-- status e status_reprodutivo (animais): aparecem em praticamente toda
-- consulta do sistema (animais ativos do usuário, em lactação, prenhas...).
-- Os dois índices compostos cobrem o padrão real de uso — sempre filtrado
-- junto com usuario_id, nunca status sozinho.
ALTER TABLE animais ADD INDEX ix_animais_status (status);
ALTER TABLE animais ADD INDEX ix_animais_status_reprodutivo (status_reprodutivo);
ALTER TABLE animais ADD INDEX ix_animais_data_prevista_parto (data_prevista_parto);
ALTER TABLE animais ADD INDEX ix_animais_usuario_status (usuario_id, status);
ALTER TABLE animais ADD INDEX ix_animais_usuario_status_reprodutivo (usuario_id, status_reprodutivo);

-- data_aplicacao (aplicações de medicamento): mesmo campo já indexado em
-- Vacina, ficou sem índice aqui por inconsistência.
ALTER TABLE aplicacoes_medicamento ADD INDEX ix_aplicacoes_data_aplicacao (data_aplicacao);