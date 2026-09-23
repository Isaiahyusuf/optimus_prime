from core.market_regime import MarketRegimeEngine
from smc.liquidity import LiquidityEngine
from smc.displacement import DisplacementEngine
from smc.structure import MarketStructure
from smc.fair_value_gaps import FairValueGapEngine
from smc.order_blocks import OrderBlockEngine
from smc.order_block_context import OrderBlockContextEngine
from strategy.setup_engine import SetupEngine


class SignalEngine:
    """
    Optimus Prime signal orchestration engine.

    Connects the deterministic SMC engines into one
    causal signal-analysis pipeline.

    Pipeline:

        Candles
            ↓
        Liquidity
            ↓
        Quality Sweep
            ↓
        Displacement
            ↓
        Market Structure
            ↓
        Market Regime
            ↓
        Order Block / FVG
            ↓
        Setup Engine
            ↓
        Valid Setups

    Market Regime is contextual only.

    It does not:
        - approve trades
        - reject trades
        - override Guardian
        - change setup validity
        - place orders
        - calculate position size
        - modify trading strategy automatically
    """

    def __init__(
        self,
        swing_length=3,
        displacement_engine=None,
        liquidity_engine=None,
        structure_engine=None,
        fvg_engine=None,
        order_block_engine=None,
        order_block_context_engine=None,
        setup_engine=None,
        market_regime_engine=None,
    ):
        self.liquidity_engine = (
            liquidity_engine
            if liquidity_engine is not None
            else LiquidityEngine()
        )

        self.displacement_engine = (
            displacement_engine
            if displacement_engine is not None
            else DisplacementEngine()
        )

        self.structure_engine = (
            structure_engine
            if structure_engine is not None
            else MarketStructure(
                swing_length=swing_length
            )
        )

        self.fvg_engine = (
            fvg_engine
            if fvg_engine is not None
            else FairValueGapEngine()
        )

        self.order_block_engine = (
            order_block_engine
            if order_block_engine is not None
            else OrderBlockEngine()
        )

        self.order_block_context_engine = (
            order_block_context_engine
            if order_block_context_engine is not None
            else OrderBlockContextEngine()
        )

        self.setup_engine = (
            setup_engine
            if setup_engine is not None
            else SetupEngine()
        )

        self.market_regime_engine = (
            market_regime_engine
            if market_regime_engine is not None
            else MarketRegimeEngine()
        )

    def _validate_candles(self, candles):
        if not isinstance(candles, list):
            return False

        if len(candles) == 0:
            return False

        return True

    def _analyze_market_regime(self, candles):
        """
        Calculate market regime context.

        Market Regime is intentionally non-blocking.

        If there are insufficient candles or the contextual
        regime calculation fails, return None rather than
        changing or blocking the SMC signal pipeline.
        """

        try:
            return self.market_regime_engine.analyze(
                candles
            )
        except Exception:
            return None

    def analyze(self, candles):
        """
        Run the complete deterministic SMC pipeline.

        Market Regime is calculated as contextual information.

        It does not approve or reject setups.

        Returns a structured analysis object.

        No trade is executed by this method.
        """

        if not self._validate_candles(candles):
            return {
                "success": False,
                "status": "NO_SIGNAL",
                "reason": "invalid_candles",
                "candles": [],
                "liquidity": [],
                "sweeps": [],
                "displacement": [],
                "structure_breaks": [],
                "market_regime": None,
                "order_blocks": [],
                "contextual_order_blocks": [],
                "fvgs": [],
                "setups": [],
                "valid_setups": [],
            }

        # --------------------------------------------------
        # 1. LIQUIDITY
        # --------------------------------------------------

        liquidity = (
            self.liquidity_engine.find_all_liquidity(
                candles
            )
        )

        # --------------------------------------------------
        # 2. QUALITY SWEEPS
        # --------------------------------------------------

        sweeps = (
            self.liquidity_engine.find_quality_sweeps(
                candles,
                liquidity,
            )
        )

        # --------------------------------------------------
        # 3. DISPLACEMENT
        # --------------------------------------------------

        displacement = (
            self.displacement_engine.detect_displacement(
                candles
            )
        )

        # --------------------------------------------------
        # 4. MARKET STRUCTURE
        # --------------------------------------------------

        structure_breaks = (
            self.structure_engine.detect_breaks(
                candles
            )
        )

        # --------------------------------------------------
        # 5. MARKET REGIME
        # --------------------------------------------------

        market_regime = (
            self._analyze_market_regime(
                candles
            )
        )

        # --------------------------------------------------
        # 6. FAIR VALUE GAPS
        # --------------------------------------------------

        fvgs = (
            self.fvg_engine.filter_quality_fvgs(
                self.fvg_engine.detect_fvgs(
                    candles
                ),
                candles,
            )
        )

        # --------------------------------------------------
        # 7. RAW ORDER BLOCKS
        # --------------------------------------------------

        raw_order_blocks = (
            self.order_block_engine.detect_order_blocks(
                candles,
                displacement,
            )
        )

        # --------------------------------------------------
        # 8. ORDER BLOCK CONTEXT
        # --------------------------------------------------

        contextual_order_blocks = (
            self.order_block_context_engine.evaluate_order_blocks(
                raw_order_blocks,
                displacement,
                structure_breaks,
            )
        )

        # --------------------------------------------------
        # 9. SETUP ENGINE
        # --------------------------------------------------

        setups = (
            self.setup_engine.evaluate_sweeps(
                sweeps,
                displacement,
                structure_breaks,
                contextual_order_blocks,
                fvgs,
            )
        )

        valid_setups = (
            self.setup_engine.filter_valid_setups(
                setups
            )
        )

        # --------------------------------------------------
        # FINAL STATUS
        # --------------------------------------------------

        if valid_setups:
            status = "SIGNALS_FOUND"
        else:
            status = "NO_SIGNAL"

        return {
            "success": True,
            "status": status,
            "reason": (
                "valid_setups_found"
                if valid_setups
                else "no_valid_setup"
            ),
            "candles": candles,
            "liquidity": liquidity,
            "sweeps": sweeps,
            "displacement": displacement,
            "structure_breaks": structure_breaks,
            "market_regime": market_regime,
            "order_blocks": raw_order_blocks,
            "contextual_order_blocks": (
                contextual_order_blocks
            ),
            "fvgs": fvgs,
            "setups": setups,
            "valid_setups": valid_setups,
        }

    def get_valid_setups(self, candles):
        """
        Convenience method returning only valid setups.
        """

        analysis = self.analyze(candles)

        return analysis["valid_setups"]

    def get_latest_valid_setup(self, candles):
        """
        Return the latest valid setup.

        Returns None when no valid setup exists.
        """

        valid_setups = self.get_valid_setups(
            candles
        )

        if not valid_setups:
            return None

        return max(
            valid_setups,
            key=lambda setup: (
                setup.get(
                    "structure",
                    {},
                ).get(
                    "candle_index",
                    -1,
                )
            ),
        )