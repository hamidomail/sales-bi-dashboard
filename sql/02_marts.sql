-- Star schema used by the dashboard.

-- Dimension: calendar
CREATE OR REPLACE TABLE dim_date AS
SELECT d::DATE AS date,
       year(d) AS year, month(d) AS month, date_trunc('week', d)::DATE AS week_start,
       date_trunc('month', d)::DATE AS month_start, strftime(d, '%a') AS weekday
FROM range((SELECT min(order_date) FROM stg_orders), (SELECT max(order_date) FROM stg_orders) + 1, INTERVAL 1 DAY) t(d);

-- Dimension: customer, with first-order cohort
CREATE OR REPLACE TABLE dim_customer AS
SELECT c.*,
       date_trunc('month', f.first_order_date)::DATE AS cohort_month,
       f.first_order_date
FROM stg_customers c
LEFT JOIN (SELECT customer_id, min(order_date) AS first_order_date FROM stg_orders GROUP BY 1) f USING (customer_id);

CREATE OR REPLACE TABLE dim_product AS SELECT * FROM stg_products;

-- Fact: one row per order line, money in EUR. Refunded lines keep gross values
-- and are netted out in net_revenue / gross_profit.
CREATE OR REPLACE TABLE fct_sales AS
SELECT l.order_id, o.order_date, o.customer_id, l.product_id, p.category,
       c.region, c.country, c.acquisition_channel AS channel, o.device,
       (o.order_number = 1) AS is_first_order,
       l.quantity,
       l.quantity * l.unit_price                                     AS gross_revenue,
       CASE WHEN l.is_refunded THEN 0 ELSE l.quantity * l.unit_price END AS net_revenue,
       CASE WHEN l.is_refunded THEN 0 ELSE l.quantity * (l.unit_price - l.unit_cost) END AS gross_profit,
       l.is_refunded,
       CASE WHEN l.is_refunded THEN l.quantity * l.unit_price ELSE 0 END AS refunded_amount
FROM stg_order_lines l
JOIN stg_orders o USING (order_id)
JOIN dim_customer c USING (customer_id)
JOIN dim_product p USING (product_id);

-- Fact: marketing spend per day & channel
CREATE OR REPLACE TABLE fct_marketing AS SELECT * FROM stg_marketing_spend;

-- Data quality checks: the build fails if any of these return rows.
CREATE OR REPLACE VIEW dq_failures AS
SELECT 'order line without order' AS check_name, count(*) AS n FROM stg_order_lines l ANTI JOIN stg_orders o USING (order_id) HAVING count(*) > 0
UNION ALL
SELECT 'order without customer', count(*) FROM stg_orders o ANTI JOIN stg_customers c USING (customer_id) HAVING count(*) > 0
UNION ALL
SELECT 'negative price or quantity', count(*) FROM stg_order_lines WHERE unit_price < 0 OR quantity <= 0 HAVING count(*) > 0
UNION ALL
SELECT 'sale below cost after discount over 60%', count(*) FROM stg_order_lines WHERE unit_price < unit_cost * 0.4 HAVING count(*) > 0
UNION ALL
SELECT 'duplicate order id', count(*) - count(DISTINCT order_id) FROM stg_orders HAVING count(*) - count(DISTINCT order_id) > 0;
