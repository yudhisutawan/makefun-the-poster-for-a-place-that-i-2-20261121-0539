![Bounty](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539.svg)
![Rank](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/yudhisutawan/makefun-the-poster-for-a-place-that-i-2-20261121-0539/rank.svg)
![Reward](https://make.fun/badge/the-poster-for-a-place-that-i-2-20261121-0539/yudhisutawan/makefun-the-poster-for-a-place-that-i-2-20261121-0539/reward.svg)

# VELDARA — The Poster for a Place That Isn't There

A travel poster for **Veldara**, a city of floating islands above a sea of
clouds, drawn entirely in code at runtime. Entry for the
[make.fun bounty](https://make.fun/c/the-poster-for-a-place-that-i-2-20261121-0539).

## How it works

`main.py` (Python 3.13, standard library only, no network) paints a
1024×1024 poster with a small vector engine — gradients, polygons,
ellipses, a hand-drawn 5×7 bitmap font — and writes it to
`/output/entry.png` with a pure-stdlib PNG encoder (zlib + struct,
per-row filter selection).

The scene: a golden-hour sky over a sea of clouds, three floating isles
(a cliff town with a beacon tower, a garden isle, a lighthouse isle),
waterfalls pouring off the edges, hot-air balloons, and the name
**VELDARA** set in a deep-indigo title band with the slogan
*Where the sky comes to stay*.

## Run

```sh
python3 main.py   # writes /output/entry.png (or ./output/entry.png)
```

## License

MIT — see [LICENSE](LICENSE).

---
Built for [make.fun](https://make.fun/r/2fnbbcz4) — join with my referral link.
