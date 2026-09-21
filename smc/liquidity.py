from __future__ import annotations

from typing import Optional


class LiquidityEngine:
    """
    Causal liquidity engine for Optimus Prime.

    Detects:
    - Confirmed swing highs/lows
    - Buy-side liquidity
    - Sell-side liquidity
    - Equal highs
    - Equal lows
    - Clustered liquidity zones
    - ATR-normalized liquidity sweeps
    - Quality liquidity sweeps

    IMPORTANT:

    A swing at candle N is only known after
    `swing_length` candles have closed.

    A liquidity level therefore cannot become active
    before its confirmation candle.

    Equal-liquidity zones are only created after both
    underlying swings have been confirmed.

    Nearby liquidity levels are clustered so that one
    market event is not incorrectly counted as several
    independent liquidity events.

    A sweep is only valid if it occurs strictly AFTER
    the liquidity zone became known.

    This prevents historical look-ahead bias.
    """

    def __init__(
        self,
        swing_length: int = 3,
        zone_tolerance_pct: float = 0.0015,
        atr_period: int = 14,
        min_penetration_atr: float = 0.10,
        max_close_distance_atr: float = 1.50,
        min_rejection_ratio: float = 0.35,
    ):
        if swing_length < 1:
            raise ValueError(
                "swing_length must be at least 1."
            )

        if zone_tolerance_pct <= 0:
            raise ValueError(
                "zone_tolerance_pct must be greater than 0."
            )

        if atr_period < 1:
            raise ValueError(
                "atr_period must be at least 1."
            )

        if min_penetration_atr < 0:
            raise ValueError(
                "min_penetration_atr cannot be negative."
            )

        if max_close_distance_atr <= 0:
            raise ValueError(
                "max_close_distance_atr must be greater than 0."
            )

        if not 0 <= min_rejection_ratio <= 1:
            raise ValueError(
                "min_rejection_ratio must be between 0 and 1."
            )

        self.swing_length = swing_length
        self.zone_tolerance_pct = zone_tolerance_pct
        self.atr_period = atr_period
        self.min_penetration_atr = min_penetration_atr
        self.max_close_distance_atr = max_close_distance_atr
        self.min_rejection_ratio = min_rejection_ratio

    # ---------------------------------------------------------
    # PRICE TOLERANCE
    # ---------------------------------------------------------

    def prices_are_similar(
        self,
        price_a: float,
        price_b: float,
    ) -> bool:
        """
        Determine whether two prices are close enough
        to belong to the same liquidity area.
        """

        if price_a <= 0 or price_b <= 0:
            return False

        difference = abs(
            price_a - price_b
        )

        average_price = (
            price_a + price_b
        ) / 2

        if average_price <= 0:
            return False

        difference_pct = (
            difference / average_price
        )

        return (
            difference_pct
            <= self.zone_tolerance_pct
        )

    # ---------------------------------------------------------
    # ATR
    # ---------------------------------------------------------

    def calculate_atr(
        self,
        candles: list[dict],
    ) -> list[Optional[float]]:
        """
        Calculate a simple rolling ATR series.

        ATR at candle N uses only candles up to N.
        """

        if not candles:
            return []

        true_ranges: list[float] = []

        for i, candle in enumerate(candles):

            high = float(candle["high"])
            low = float(candle["low"])

            if i == 0:
                true_ranges.append(
                    high - low
                )
                continue

            previous_close = float(
                candles[i - 1]["close"]
            )

            true_range = max(
                high - low,
                abs(
                    high - previous_close
                ),
                abs(
                    low - previous_close
                ),
            )

            true_ranges.append(
                true_range
            )

        atr: list[Optional[float]] = [
            None
        ] * len(candles)

        for i in range(len(candles)):

            start = (
                i - self.atr_period + 1
            )

            if start < 0:
                continue

            window = true_ranges[
                start:i + 1
            ]

            if not window:
                continue

            atr[i] = (
                sum(window)
                / len(window)
            )

        return atr

    # ---------------------------------------------------------
    # SWING DETECTION
    # ---------------------------------------------------------

    def detect_swings(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect confirmed swing highs and lows.

        Swing at N:

            N
            ↓
            wait for swing_length candles
            ↓
            N + swing_length
            ↓
            confirmed

        No swing is considered known before its
        confirmation candle.
        """

        required = (
            self.swing_length * 2
        ) + 1

        if len(candles) < required:
            raise ValueError(
                f"Need at least {required} candles."
            )

        swings: list[dict] = []

        length = self.swing_length

        for i in range(
            length,
            len(candles) - length,
        ):

            current = candles[i]

            left = candles[
                i - length:i
            ]

            right = candles[
                i + 1:i + length + 1
            ]

            current_high = float(
                current["high"]
            )

            current_low = float(
                current["low"]
            )

            is_swing_high = all(
                current_high
                > float(candle["high"])
                for candle in (
                    left + right
                )
            )

            is_swing_low = all(
                current_low
                < float(candle["low"])
                for candle in (
                    left + right
                )
            )

            # A candle that qualifies as both is ignored.
            if (
                is_swing_high
                and is_swing_low
            ):
                continue

            confirmation_index = (
                i + length
            )

            confirmation_timestamp = (
                candles[
                    confirmation_index
                ]["timestamp"]
            )

            if is_swing_high:

                swings.append(
                    {
                        "type": "swing_high",
                        "index": i,
                        "confirmed_at_index": (
                            confirmation_index
                        ),
                        "timestamp": (
                            current["timestamp"]
                        ),
                        "confirmation_timestamp": (
                            confirmation_timestamp
                        ),
                        "price": current_high,
                    }
                )

            elif is_swing_low:

                swings.append(
                    {
                        "type": "swing_low",
                        "index": i,
                        "confirmed_at_index": (
                            confirmation_index
                        ),
                        "timestamp": (
                            current["timestamp"]
                        ),
                        "confirmation_timestamp": (
                            confirmation_timestamp
                        ),
                        "price": current_low,
                    }
                )

        return swings

    # ---------------------------------------------------------
    # SWING LIQUIDITY
    # ---------------------------------------------------------

    def find_swing_liquidity(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Convert confirmed swings into liquidity levels.
        """

        swings = self.detect_swings(
            candles
        )

        liquidity: list[dict] = []

        for swing in swings:

            if swing["type"] == "swing_high":

                liquidity_type = "buy_side"
                subtype = "swing_high"

            else:

                liquidity_type = "sell_side"
                subtype = "swing_low"

            liquidity.append(
                {
                    "type": liquidity_type,
                    "subtype": subtype,
                    "price": swing["price"],
                    "index": swing["index"],
                    "confirmed_at_index": (
                        swing[
                            "confirmed_at_index"
                        ]
                    ),
                    "timestamp": (
                        swing["timestamp"]
                    ),
                    "confirmation_timestamp": (
                        swing[
                            "confirmation_timestamp"
                        ]
                    ),
                    "source": "swing",
                }
            )

        return liquidity

    # ---------------------------------------------------------
    # EQUAL LIQUIDITY
    # ---------------------------------------------------------

    def find_equal_liquidity(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect equal highs and equal lows.

        The second swing must already be confirmed before
        the equal-liquidity zone becomes active.

        This prevents future information from creating
        historical liquidity.
        """

        swings = self.detect_swings(
            candles
        )

        highs = [
            swing
            for swing in swings
            if swing["type"]
            == "swing_high"
        ]

        lows = [
            swing
            for swing in swings
            if swing["type"]
            == "swing_low"
        ]

        liquidity: list[dict] = []

        # -----------------------------------------------------
        # Equal highs = buy-side liquidity
        # -----------------------------------------------------

        for i in range(len(highs)):

            for j in range(
                i + 1,
                len(highs),
            ):

                first = highs[i]
                second = highs[j]

                if not self.prices_are_similar(
                    first["price"],
                    second["price"],
                ):
                    continue

                confirmation_index = max(
                    first[
                        "confirmed_at_index"
                    ],
                    second[
                        "confirmed_at_index"
                    ],
                )

                confirmation_timestamp = (
                    candles[
                        confirmation_index
                    ]["timestamp"]
                )

                average_price = (
                    first["price"]
                    + second["price"]
                ) / 2

                liquidity.append(
                    {
                        "type": "buy_side",
                        "subtype": "equal_high",
                        "price": average_price,
                        "index": second[
                            "index"
                        ],
                        "confirmed_at_index": (
                            confirmation_index
                        ),
                        "timestamp": (
                            second["timestamp"]
                        ),
                        "confirmation_timestamp": (
                            confirmation_timestamp
                        ),
                        "source": "equal_high",
                        "sources": 2,
                        "source_indices": [
                            first["index"],
                            second["index"],
                        ],
                    }
                )

        # -----------------------------------------------------
        # Equal lows = sell-side liquidity
        # -----------------------------------------------------

        for i in range(len(lows)):

            for j in range(
                i + 1,
                len(lows),
            ):

                first = lows[i]
                second = lows[j]

                if not self.prices_are_similar(
                    first["price"],
                    second["price"],
                ):
                    continue

                confirmation_index = max(
                    first[
                        "confirmed_at_index"
                    ],
                    second[
                        "confirmed_at_index"
                    ],
                )

                confirmation_timestamp = (
                    candles[
                        confirmation_index
                    ]["timestamp"]
                )

                average_price = (
                    first["price"]
                    + second["price"]
                ) / 2

                liquidity.append(
                    {
                        "type": "sell_side",
                        "subtype": "equal_low",
                        "price": average_price,
                        "index": second[
                            "index"
                        ],
                        "confirmed_at_index": (
                            confirmation_index
                        ),
                        "timestamp": (
                            second["timestamp"]
                        ),
                        "confirmation_timestamp": (
                            confirmation_timestamp
                        ),
                        "source": "equal_low",
                        "sources": 2,
                        "source_indices": [
                            first["index"],
                            second["index"],
                        ],
                    }
                )

        return liquidity

    # ---------------------------------------------------------
    # LIQUIDITY CLUSTERING
    # ---------------------------------------------------------

    def cluster_liquidity(
        self,
        levels: list[dict],
    ) -> list[dict]:
        """
        Merge nearby liquidity levels into meaningful zones.

        Only liquidity from the same side is clustered.

        Example:

            buy-side 100.00
            buy-side 100.08
            buy-side 100.12

        becomes:

            buy-side liquidity cluster ≈ 100.07

        The cluster retains information about the original
        liquidity sources.

        IMPORTANT:

        The cluster confirmation time is the latest
        confirmation time among its members.

        Therefore the cluster cannot become available
        before all information used to construct it
        was actually known.
        """

        if not levels:
            return []

        sorted_levels = sorted(
            levels,
            key=lambda level: (
                level[
                    "confirmed_at_index"
                ],
                level["index"],
            ),
        )

        clusters: list[list[dict]] = []

        for level in sorted_levels:

            placed = False

            for cluster in clusters:

                # Never combine buy-side and sell-side
                # liquidity.
                if (
                    cluster[0]["type"]
                    != level["type"]
                ):
                    continue

                cluster_prices = [
                    float(item["price"])
                    for item in cluster
                ]

                cluster_average = (
                    sum(cluster_prices)
                    / len(cluster_prices)
                )

                if self.prices_are_similar(
                    cluster_average,
                    float(level["price"]),
                ):

                    cluster.append(
                        level
                    )

                    placed = True
                    break

            if not placed:

                clusters.append(
                    [level]
                )

        clustered: list[dict] = []

        for cluster in clusters:

            prices = [
                float(level["price"])
                for level in cluster
            ]

            average_price = (
                sum(prices)
                / len(prices)
            )

            latest_confirmation = max(
                level[
                    "confirmed_at_index"
                ]
                for level in cluster
            )

            latest_level = max(
                cluster,
                key=lambda level: (
                    level[
                        "confirmed_at_index"
                    ],
                    level["index"],
                ),
            )

            source_indices: list[int] = []

            for level in cluster:

                if (
                    "source_indices"
                    in level
                ):

                    source_indices.extend(
                        level[
                            "source_indices"
                        ]
                    )

                else:

                    source_indices.append(
                        level["index"]
                    )

            source_indices = sorted(
                set(source_indices)
            )

            source_types = sorted(
                set(
                    level["source"]
                    for level in cluster
                )
            )

            source_subtypes = sorted(
                set(
                    level["subtype"]
                    for level in cluster
                )
            )

            clustered.append(
                {
                    "type": cluster[0]["type"],
                    "subtype": (
                        "liquidity_cluster"
                    ),
                    "price": average_price,

                    # Representative index.
                    "index": max(
                        level["index"]
                        for level in cluster
                    ),

                    # CRITICAL CAUSALITY RULE:
                    # The cluster only exists after
                    # every source level is confirmed.
                    "confirmed_at_index": (
                        latest_confirmation
                    ),

                    "timestamp": (
                        latest_level[
                            "timestamp"
                        ]
                    ),

                    "confirmation_timestamp": (
                        latest_level[
                            "confirmation_timestamp"
                        ]
                    ),

                    "source": "cluster",

                    "sources": len(cluster),

                    "source_types": (
                        source_types
                    ),

                    "source_subtypes": (
                        source_subtypes
                    ),

                    "source_indices": (
                        source_indices
                    ),
                }
            )

        clustered.sort(
            key=lambda level: (
                level[
                    "confirmed_at_index"
                ],
                level["index"],
            )
        )

        return clustered

    # ---------------------------------------------------------
    # ALL LIQUIDITY
    # ---------------------------------------------------------

    def find_all_liquidity(
        self,
        candles: list[dict],
    ) -> list[dict]:
        """
        Detect raw liquidity and convert it into
        clustered liquidity zones.
        """

        swing_levels = (
            self.find_swing_liquidity(
                candles
            )
        )

        equal_levels = (
            self.find_equal_liquidity(
                candles
            )
        )

        raw_levels = (
            swing_levels
            + equal_levels
        )

        return self.cluster_liquidity(
            raw_levels
        )

    # ---------------------------------------------------------
    # SWEEP METRICS
    # ---------------------------------------------------------

    def calculate_sweep_metrics(
        self,
        candle: dict,
        liquidity: dict,
        atr: Optional[float],
    ) -> Optional[dict]:
        """
        Calculate penetration, close distance and rejection
        metrics for a potential liquidity sweep.
        """

        if atr is None or atr <= 0:
            return None

        high = float(
            candle["high"]
        )

        low = float(
            candle["low"]
        )

        close = float(
            candle["close"]
        )

        open_price = float(
            candle["open"]
        )

        liquidity_price = float(
            liquidity["price"]
        )

        liquidity_type = (
            liquidity["type"]
        )

        candle_range = (
            high - low
        )

        if candle_range <= 0:
            return None

        # -----------------------------------------------------
        # Buy-side liquidity
        # -----------------------------------------------------

        if liquidity_type == "buy_side":

            penetration = (
                high
                - liquidity_price
            )

            if penetration <= 0:
                return None

            close_distance = abs(
                close
                - liquidity_price
            )

            rejection_distance = max(
                high - close,
                0.0,
            )

            direction = "bearish"

        # -----------------------------------------------------
        # Sell-side liquidity
        # -----------------------------------------------------

        elif liquidity_type == "sell_side":

            penetration = (
                liquidity_price
                - low
            )

            if penetration <= 0:
                return None

            close_distance = abs(
                close
                - liquidity_price
            )

            rejection_distance = max(
                close - low,
                0.0,
            )

            direction = "bullish"

        else:
            return None

        penetration_pct = (
            penetration
            / liquidity_price
            if liquidity_price > 0
            else 0.0
        )

        penetration_atr = (
            penetration
            / atr
        )

        close_distance_atr = (
            close_distance
            / atr
        )

        rejection_ratio = (
            rejection_distance
            / candle_range
        )

        return {
            "penetration": penetration,
            "penetration_pct": (
                penetration_pct
            ),
            "penetration_atr": (
                penetration_atr
            ),
            "close_distance": (
                close_distance
            ),
            "close_distance_atr": (
                close_distance_atr
            ),
            "rejection_ratio": (
                rejection_ratio
            ),
            "atr": atr,
            "direction": direction,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        }

    # ---------------------------------------------------------
    # SWEEP DETECTION
    # ---------------------------------------------------------

    def detect_sweeps(
        self,
        candles: list[dict],
        liquidity_levels: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Detect liquidity sweeps.

        A liquidity zone cannot be swept on the same candle
        that confirms it.

        The sweep must occur strictly AFTER confirmation.

        Each clustered liquidity zone can only be consumed
        once by the first valid sweep.
        """

        if not candles:
            return []

        if liquidity_levels is None:

            liquidity_levels = (
                self.find_all_liquidity(
                    candles
                )
            )

        atr_series = (
            self.calculate_atr(
                candles
            )
        )

        sweeps: list[dict] = []

        # Each cluster can only produce one
        # first valid sweep.
        consumed: set[tuple] = set()

        for candle_index, candle in enumerate(
            candles
        ):

            atr = atr_series[
                candle_index
            ]

            if atr is None or atr <= 0:
                continue

            for liquidity in (
                liquidity_levels
            ):

                confirmation_index = (
                    liquidity[
                        "confirmed_at_index"
                    ]
                )

                # CRITICAL CAUSALITY RULE:
                #
                # The liquidity must have been
                # confirmed BEFORE the sweep candle.
                #
                # Same-candle confirmation is not allowed.
                if (
                    candle_index
                    <= confirmation_index
                ):
                    continue

                zone_key = (
                    liquidity["type"],
                    liquidity["subtype"],
                    liquidity["index"],
                    round(
                        float(
                            liquidity["price"]
                        ),
                        8,
                    ),
                    tuple(
                        liquidity.get(
                            "source_indices",
                            [],
                        )
                    ),
                )

                if zone_key in consumed:
                    continue

                metrics = (
                    self.calculate_sweep_metrics(
                        candle,
                        liquidity,
                        atr,
                    )
                )

                if metrics is None:
                    continue

                if (
                    metrics[
                        "penetration_atr"
                    ]
                    < self.min_penetration_atr
                ):
                    continue

                if (
                    metrics[
                        "close_distance_atr"
                    ]
                    > self.max_close_distance_atr
                ):
                    continue

                if (
                    metrics[
                        "rejection_ratio"
                    ]
                    < self.min_rejection_ratio
                ):
                    continue

                sweep = {
                    "type": (
                        f'{liquidity["type"]}'
                        "_sweep"
                    ),

                    "direction": (
                        metrics[
                            "direction"
                        ]
                    ),

                    "candle_index": (
                        candle_index
                    ),

                    "timestamp": (
                        candle["timestamp"]
                    ),

                    "price": (
                        candle["close"]
                    ),

                    "liquidity_index": (
                        liquidity["index"]
                    ),

                    "liquidity_price": (
                        liquidity["price"]
                    ),

                    "liquidity_type": (
                        liquidity["type"]
                    ),

                    "liquidity_subtype": (
                        liquidity["subtype"]
                    ),

                    "liquidity_source": (
                        liquidity["source"]
                    ),

                    "liquidity_confirmed_at_index": (
                        confirmation_index
                    ),

                    "liquidity_confirmation_timestamp": (
                        liquidity[
                            "confirmation_timestamp"
                        ]
                    ),

                    **metrics,
                }

                # Preserve cluster metadata.
                if "sources" in liquidity:

                    sweep["sources"] = (
                        liquidity[
                            "sources"
                        ]
                    )

                if "source_types" in liquidity:

                    sweep["source_types"] = (
                        liquidity[
                            "source_types"
                        ]
                    )

                if "source_subtypes" in liquidity:

                    sweep["source_subtypes"] = (
                        liquidity[
                            "source_subtypes"
                        ]
                    )

                if "source_indices" in liquidity:

                    sweep["source_indices"] = (
                        liquidity[
                            "source_indices"
                        ]
                    )

                sweeps.append(
                    sweep
                )

                # First valid sweep consumes
                # the entire liquidity cluster.
                consumed.add(
                    zone_key
                )

        sweeps.sort(
            key=lambda sweep: (
                sweep[
                    "candle_index"
                ],
                sweep[
                    "liquidity_type"
                ],
                sweep[
                    "liquidity_price"
                ],
            )
        )

        return sweeps

    # ---------------------------------------------------------
    # QUALITY SWEEPS
    # ---------------------------------------------------------

    def find_quality_sweeps(
        self,
        candles: list[dict],
        liquidity_levels: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Return sweeps satisfying the configured
        quality filters.
        """

        return self.detect_sweeps(
            candles,
            liquidity_levels,
        )