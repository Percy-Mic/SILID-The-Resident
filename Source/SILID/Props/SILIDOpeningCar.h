// The Act I opening sequence as a world actor.
//
// The prototype's opening.js runs the whole Act I prelude as one state
// machine attached to the car: drive, engine failure, coast to the shoulder,
// stop, exit, and three roadside interactions (hood / ignition / boot). This
// class is that state machine in Unreal — same phases, same cue timing, same
// messages, adapted to the engine's own primitives.
//
// Geography (all verified by trace probes in BuildExteriorWorldPMC.py):
//   road centreline: x = -62 + 3.2*sin((z-10)*0.012) + 1.4*sin(z*0.031)
//   start point:     z = -78, in the northbound lane, +1.7 from centre
//   pull-off:        z = -6,  west shoulder, -4.3 from centreline
//   the car actor placed by the build script faces north (yaw 90).
//
// Phases:
//   Idle -> Driving -> Failing -> Stopped -> Exiting -> Walk
// Driving and Failing integrate the car at 30 Hz fixed steps (prototype
// behaviour) so the drive feels identical at 30 or 120 fps.

#pragma once

#include "GameFramework/Actor.h"
#include "Systems/SILIDInterfaces.h"
#include "SILIDOpeningCar.generated.h"

class UStaticMeshComponent;
class USpotLightComponent;
class UPointLightComponent;
class UBoxComponent;
class ASILIDCharacter;
class USILIDItemData;
class USILIDInventoryComponent;

/** Opening-sequence lifecycle (prototype opening.js phases). */
UENUM(BlueprintType)
enum class EOpeningPhase : uint8
{
	Idle     UMETA(DisplayName = "Idle"),
	Driving  UMETA(DisplayName = "Driving"),
	Failing  UMETA(DisplayName = "Failing"),
	Stopped  UMETA(DisplayName = "Stopped"),
	Exiting  UMETA(DisplayName = "Exiting"),
	Walk     UMETA(DisplayName = "Walk")
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnOpeningMessage, const FText&, Message);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnOpeningWalkPhase);

UCLASS()
class SILID_API ASILIDOpeningCar : public AActor, public ISILIDInteractable
{
	GENERATED_BODY()

public:
	ASILIDOpeningCar();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Car")
	TObjectPtr<UStaticMeshComponent> Body;

	/** Roadside interaction volumes: hood, ignition (through the windscreen), boot. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Car")
	TObjectPtr<UBoxComponent> HoodFocus;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Car")
	TObjectPtr<UBoxComponent> IgnitionFocus;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Car")
	TObjectPtr<UBoxComponent> BootFocus;

	/** Real headlight beams: two spots parented to the body. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Car")
	TObjectPtr<USpotLightComponent> HeadLeft;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Card")
	TObjectPtr<USpotLightComponent> HeadRight;

	/** Hazard pulse light, dead engine bay ambience. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Car")
	TObjectPtr<UPointLightComponent> HazardLight;

	/** Speeds: a narrow provincial road, not a highway (prototype MAX_SPEED). */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float MaxSpeed = 555.f;            // cm/s (5.55 m/s driving feel; prototype 15.5 m/s tune in JS used throttle curve)
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float ThrottleAccel = 340.f;       // cm/s^2
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float BrakeDecel = 700.f;          // cm/s^2
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float RollingDrag = 0.14f;         // fraction per second while driving
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float CoastDrag = 0.30f;           // fraction per second while failing
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float CoastLinear = 55.f;          // cm/s^2 constant rolling loss while failing
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float TriggerDistance = 4500.f;    // metres driven *100 before the fault can fire
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float TriggerZ = -3400.f;          // ...but only once level with this plan z
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float PullZ = -600.f;              // the shoulder the car ends up on
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Car|Tuning")
	float PullOffset = -430.f;         // west shoulder offset from centreline

	/** Message line the HUD shows (prototype: game.say(...)). */
	UPROPERTY(BlueprintAssignable, Category = "Car|Events")
	FOnOpeningMessage OnOpeningMessage;

	/** Fired when the sequence completes and the player takes control on foot. */
	UPROPERTY(BlueprintAssignable, Category = "Car|Events")
	FOnOpeningWalkPhase OnWalkPhaseStarted;

	virtual bool Interact(ASILIDCharacter* Player) override;
	virtual bool CanInteract(const ASILIDCharacter* Player) const override;
	virtual FText GetInteractionText(const ASILIDCharacter* Player) const override;
	virtual FText GetExamineText(const ASILIDCharacter* Player) const override;
	virtual void OnFocus() override;
	virtual void OnUnfocus() override;

	/** Test hook: fire the failure immediately from wherever the car is. */
	UFUNCTION(BlueprintCallable, Category = "Car")
	void ForceBreakdown();

	/** Start the Act I drive: called by the game mode when the exterior map
	 * opens. Puts the sequence into the driving phase with Del at the wheel. */
	UFUNCTION(BlueprintCallable, Category = "Car")
	void BeginSequence();

	/** Feed the drive inputs directly (controller routing, Phase 2.2).
	 * ThrottleAxis/SteerAxis in -1..1 (WASD convention); Brake is S held.
	 * While the controller feeds this, StepDrive consumes it instead of the
	 * character's last-movement vector. Cleared when the drive ends. */
	void SetDriveInput(float ThrottleAxis, float SteerAxis, bool bBrake);

	/** True while the drive (or the coast) is live and input belongs to the car. */
	UFUNCTION(BlueprintPure, Category = "Car")
	bool IsDrivingPhase() const
	{
		return Phase == EOpeningPhase::Driving || Phase == EOpeningPhase::Failing;
	}

	UFUNCTION(BlueprintPure, Category = "Car")
	bool IsWalkPhase() const { return Phase == EOpeningPhase::Walk; }

	UFUNCTION(BlueprintPure, Category = "Car")
	EOpeningPhase GetPhase() const { return Phase; }

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaTime) override;

private:
	EOpeningPhase Phase = EOpeningPhase::Idle;
	float X = 0.f;                 // plan x, cm
	float Z = 0.f;                 // plan z, cm
	float Heading = 0.f;           // radians; 0 = north (+Y)
	float Speed = 0.f;             // cm/s (signed: negative = reverse)
	float Steer = 0.f;
	float Travelled = 0.f;         // cm driven
	float FailT = 0.f;
	float DeadT = 0.f;
	float DoorT = 0.f;
	float HazT = 0.f;
	float FixedAcc = 0.f;
	bool ThrottleCut = false;
	bool HazardsOn = false;
	bool SaidDead = false;
	bool CueA = false, CueB = false, CueC = false;
	bool HoodChecked = false, RestartTried = false, BootChecked = false;
	bool CollidersAdded = false;
	bool Autodrive = false;   // -SILIDAUTODRIVE: headless receipt runs
	float DriveLogAcc = 0.f;  // once-per-second motion receipt accumulator

	// direct controller input (Phase 2.2): fed by SetDriveInput each frame
	float DriveThrottleIn = 0.f;  // -1..1 (W/S)
	float DriveSteerIn = 0.f;     // -1..1 (A/D, same sign convention as StepDrive's SteerIn)
	bool DriveBrakeIn = false;    // S held past the reverse threshold
	bool bHasDirectDriveInput = false;
	float DriveInputAge = 0.f;    // seconds since the controller last fed input

	void Integrate(float Dt, float YawRate);
	bool CarBlocked(float Nx, float Nz, float Gy) const;
	float HeightAtPlan(float PlanX, float PlanZ) const;
	float RoadCenter(float PlanZ) const;
	void BeginFail();
	void Stop();
	void FinishExit();
	void SyncCarTransform();
	void SetPhase(EOpeningPhase NewPhase);

	// fixed-step integrators (prototype _drive / _fail / _deadCues)
	void StepDrive(float Dt);
	void StepFail(float Dt);
	void StepStopped(float Dt);
};
