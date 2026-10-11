select n.nspname as esquema,
       count(*) filter (where c.relkind in ('r','p')) as tablas,
       pg_size_pretty(sum(pg_total_relation_size(c.oid))
                      filter (where c.relkind in ('r','p'))) as tamano_total
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname in ('staging', 'silver', 'gold')
group by n.nspname
order by n.nspname;

select n.nspname as esquema, c.relname as tabla,
       c.reltuples::bigint as filas_aprox,
       pg_size_pretty(pg_total_relation_size(c.oid)) as tamano
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname in ('staging', 'silver', 'gold') and c.relkind in ('r','p')
order by pg_total_relation_size(c.oid) desc
limit 25;
