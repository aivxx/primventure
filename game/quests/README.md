# Primventure Quest Catalog

The catalog contains 39 quests across Floors 0–9. Floor 3 is the first expanded
floor, with four curriculum neighborhoods, their bosses, a city boss, and a
multi-arc LIVRPS floor boss; the remaining floors currently provide three
representative quests each. Files are ordered by floor, and `prerequisites` form a playable path from
`f0_first_prim` through `f9_null_monarch`. Exchange and Instancing branch after
Floor 6 and both must be cleared before Floor 9. Boss encounters are distributed
throughout the route using `neighborhood_boss`, `city_boss`, and `floor_boss`;
ordinary encounters use `room`.

Each floor file has `floor`, `floor_name`, and a `quests` sequence. Every quest
provides:

- Identity and routing: `id`, `title`, `floor`, `floor_name`, `neighborhood`,
  `kind`, `prerequisites`, `level_required`, and `world_target`.
- Learning content: `exam_tasks`, `brief`, executable `starter`, `language`,
  `cookbook`, and `recipes`. `questions` is optional.
- Progression: `stats`, `xp`, and `reward`.
- Grading: `validator.assertions`, a list of single-key declarative assertions.

Supported assertion keys are `prim_exists`, `prim_type`, `attribute_equals`,
`metadata_equals`, `has_reference`, `has_payload`, `has_variant_set`,
`has_inherit`, `has_specializes`, `instanceable`, `specifier_equals`,
`prim_stack`, `sublayer_order`, `attribute_source`, `traversal_contains`,
`default_prim`, `up_axis`, `start_time`, and `end_time`.
Scalar assertions carry the expected value directly. Object assertions include
`path` plus the expected `value`, `asset`, `name`, variants, selection, time,
metadata key, or nested field as applicable.

Python starters expect the runner to inject `STAGE_PATH`. USDA starters are
complete text documents that the runner writes to that path. Cookbook values
are repository-relative paths to Learn OpenUSD lessons. Successful submissions
are published as bundles so any supporting layers authored beside `STAGE_PATH`
remain inspectable in the persistent portfolio.
