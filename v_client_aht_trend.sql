-- sql/views/v_client_aht_trend.sql
CREATE OR REPLACE VIEW v_client_aht_trend AS
SELECT
    client_id,
    DATE(interaction_timestamp) AS metric_date,
    AVG(handle_time_seconds) AS metric_value
FROM fact_interactions
WHERE interaction_type = 'inbound'
GROUP BY 1, 2;