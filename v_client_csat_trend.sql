-- sql/views/v_client_csat_trend.sql
CREATE OR REPLACE VIEW v_client_csat_trend AS
SELECT
    client_id,
    DATE(survey_timestamp) AS metric_date,
    AVG(csat_score) AS metric_value
FROM fact_surveys
WHERE csat_score IS NOT NULL
GROUP BY 1, 2;