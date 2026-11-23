<script lang="ts">
  // The production plan of a farm profile (schedule.json from the worker), in the
  // order of the level plan page: key figures, login times, last login, trees and
  // bushes, outside goods, then the login actions per building, collapsed.
  import type { Combined, LoginAction, LoginItem } from "../data";
  import { content, fill, hours, number, type Lang } from "../i18n";
  import { label } from "../paths";

  type Schedule = Combined["schedule"];
  interface Props {
    schedule: Schedule;
    lang: Lang;
  }
  let { schedule: s, lang }: Props = $props();

  const c = $derived(content(lang));
  const t = $derived(c.level);
  const actions = $derived(c.actions as Record<string, string>);
  const whats = $derived(c.whats as Record<string, string>);

  interface Group {
    id: string;
    name: string;
    kind?: string;
    slots?: number;
    list: LoginAction[];
  }

  const figures = $derived([
    [t.loginsPerDay, number(s.logins_per_day, lang)],
    [t.dayGap, hours(s.day_gap_hours, lang)],
    [t.nightGap, hours(s.night_gap_hours, lang)],
    [
      t.fieldsUsed,
      fill(t.fieldsOf, { used: s.recommendations.fields.used_by_plan, owned: s.recommendations.fields.owned }),
    ],
  ]);
  const trees = $derived(Object.entries(s.recommendations.trees_and_bushes));
  const external = $derived(Object.entries(s.external_per_day));
  const groups = $derived.by(() => {
    const out: Group[] = [];
    for (const a of s.actions_per_login) {
      const id = a.location_id ?? a.action;
      const group = out.find((g) => g.id === id);
      if (group) {
        group.list.push(a);
        group.slots ??= a.slots;
      } else {
        out.push({
          id,
          name: a.location_id ? label(a.location_id) : (actions[a.action] ?? label(a.action)),
          kind: a.location_id ? (actions[a.action] ?? label(a.action)) : undefined,
          slots: a.slots,
          list: [a],
        });
      }
    }
    return out;
  });
  const itemCount = (g: Group) => g.list.reduce((n, a) => n + (a.items?.length ?? 0), 0);
  const itemName = (item: Pick<LoginItem, "recipe_id" | "resource_id">) =>
    label(item.recipe_id ?? item.resource_id ?? "?");
</script>

<div data-testid="profile-plan">
  <dl class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
    {#each figures as [name, value] (name)}
      <div class="tile">
        <dt class="muted text-sm">{name}</dt>
        <dd class="font-display text-xl font-semibold">{value}</dd>
      </div>
    {/each}
  </dl>
  <h3 class="mt-5 text-lg">{t.loginTimes}</h3>
  <ol class="item-list mt-2" data-testid="login-times">
    {#each s.login_times as time (time)}
      <li class="item"><time>{time}</time></li>
    {/each}
  </ol>
  {#if s.last_login && s.last_login.items.length > 0}
    <h3 class="mt-5 text-lg">{fill(t.lastLogin, { time: s.last_login.time })}</h3>
    <ul class="item-list mt-2">
      {#each s.last_login.items as item, i (i)}
        <li class="item">
          {itemName(item)}
          {#if item.location_id}<span class="every">{label(item.location_id)}</span>{/if}
          <b>{hours(item.hours, lang)}</b>
        </li>
      {/each}
    </ul>
  {/if}
  {#if trees.length > 0}
    <p class="mt-5">{t.trees} {trees.map(([id, tree]) => `${label(id)} ${tree.plants}`).join(", ")}.</p>
  {/if}
  {#if external.length > 0}
    <p class="mt-2">{t.external} {external.map(([id, n]) => `${label(id)} ${number(n, lang)}`).join(", ")}.</p>
  {/if}

  <h3 class="mt-6 text-lg">{t.logins}</h3>
  <p class="muted mt-1">{t.loginsHint}</p>
  <ol class="mt-3 grid gap-3">
    {#each groups as g, i (g.id)}
      <li>
        <details class="tile login-group">
          <summary class="flex cursor-pointer items-center gap-3">
            <span class="step-no shrink-0">{i + 1}</span>
            <span class="min-w-0 grow">
              <span class="font-display text-lg font-semibold">{g.name}</span>
              <span class="muted block text-sm">
                {[
                  g.kind,
                  g.slots ? fill(t.slots, { n: g.slots }) : "",
                  itemCount(g) ? fill(t.items, { n: itemCount(g) }) : "",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </span>
          </summary>
          <div class="pt-3">
            {#each g.list as a, j (j)}
              <div class="mt-2 first:mt-0">
                {#if g.list.length > 1}<p class="font-semibold">{actions[a.action] ?? label(a.action)}</p>{/if}
                {#if a.what}<p>{whats[a.what] ?? a.what}</p>{/if}
                {#if a.items}
                  <ul class="item-list mt-2">
                    {#each a.items as item, k (k)}
                      <li class="item">
                        {itemName(item)} <b>{item.count ?? item.per_login}</b>
                        {#if item.every_n_logins}
                          <span class="every">{fill(t.everyN, { n: item.every_n_logins })}</span>
                        {/if}
                      </li>
                    {/each}
                  </ul>
                {/if}
              </div>
            {/each}
          </div>
        </details>
      </li>
    {/each}
  </ol>
</div>

<style>
  .login-group summary {
    list-style: none;
  }
  .login-group summary::-webkit-details-marker {
    display: none;
  }
</style>
