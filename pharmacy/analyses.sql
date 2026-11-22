-- Задание 5, MySQL 8. Запусти весь файл для демонстрации в одной сессии.
-- Демонстрационная таблица существует только до закрытия соединения.
DROP TEMPORARY TABLE IF EXISTS analyses;
CREATE TEMPORARY TABLE analyses (
    patient_id INT NOT NULL,
    analysis_date DATETIME NOT NULL,
    indicator VARCHAR(64) NOT NULL,
    value DECIMAL(10,3) NOT NULL,
    norm_min DECIMAL(10,3) NOT NULL,
    norm_max DECIMAL(10,3) NOT NULL,
    PRIMARY KEY (patient_id, indicator, analysis_date)
) DEFAULT CHARSET=utf8mb4;

INSERT INTO analyses (patient_id, analysis_date, indicator, value, norm_min, norm_max) VALUES
    (1, '2026-09-01', 'А', 8, 4, 6),
    (1, '2026-09-10', 'А', 9, 4, 6),
    (1, '2026-09-20', 'А', 5, 4, 6),
    (1, '2026-09-01', 'Б', 5, 4, 6),
    (1, '2026-09-20', 'Б', 8, 4, 6),
    (2, '2026-09-01', 'А', 4, 4, 6),
    (2, '2026-09-20', 'А', 6, 4, 6),
    (3, '2026-09-01', 'А', 0, 1, 3),
    (3, '2026-09-20', 'А', 2, 1, 3),
    (4, '2026-09-01', 'А', 7, 4, 6),
    (4, '2026-09-20', 'Б', 5, 4, 6);

-- Итоговый запрос. Для существующей таблицы выполни только блок от WITH до конца.
WITH comparison AS (
    SELECT patient_id, indicator,
           FIRST_VALUE(value) OVER history AS first_result,
           value AS last_result,
           FIRST_VALUE(value BETWEEN norm_min AND norm_max) OVER history AS first_normal,
           (value BETWEEN norm_min AND norm_max) AS last_normal,
           ROW_NUMBER() OVER history AS measurement_no,
           LEAD(analysis_date) OVER history AS next_date
    FROM analyses
    WINDOW history AS (PARTITION BY patient_id, indicator ORDER BY analysis_date)
)
SELECT patient_id, indicator, first_result, last_result,
       ROUND((last_result - first_result) * 100 / NULLIF(first_result, 0), 2) AS change_percent,
       CASE
           WHEN first_normal = 0 AND last_normal = 1 THEN 'вошёл в норму'
           WHEN first_normal = 1 AND last_normal = 0 THEN 'вышел из нормы'
           ELSE 'без изменений'
       END AS status
FROM comparison
WHERE next_date IS NULL AND measurement_no >= 2
ORDER BY patient_id, indicator;
