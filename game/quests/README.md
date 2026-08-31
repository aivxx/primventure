# Primventure Quest Catalog

The catalog currently contains 73 quests across Floors 0–9. Floors 3–9
are expanded. Floor 4 is Beyond-Basics Gardens (primvars, custom properties,
active/inactive, traversal, units, kinds, Hydra concept). Floor 9 is the Certification
Colosseum: live debug (edit targets, stacks, layer offsets, flatten,
ChangeBlock) plus honest Customizing USD / Hydra concept raids. Original MCQs
are mapped to study-guide task IDs 1.1–8.x. Files are ordered by floor, and `prerequisites` form a playable path from
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
`kind_equals`, `meters_per_unit`, `point_instancer`, `layer_offset`,
`default_prim`, `up_axis`, `active`, `start_time`, and `end_time`.
`metadata_equals` may include `field` to read a key from dictionary metadata
such as `assetInfo` or `customData`.
Scalar assertions carry the expected value directly. Object assertions include
`path` plus the expected `value`, `asset`, `name`, variants, selection, time,
metadata key, or nested field as applicable.

Python starters expect the runner to inject `STAGE_PATH`. USDA starters are
complete text documents that the runner writes to that path. Cookbook values
are repository-relative paths to Learn OpenUSD lessons. Successful submissions
are published as bundles so any supporting layers authored beside `STAGE_PATH`
remain inspectable in the persistent portfolio.
