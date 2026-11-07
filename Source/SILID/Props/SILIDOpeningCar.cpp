// The Act I opening sequence, implemented (see the header for the geography,
// phase list, and the prototype correspondence).
//
// Del drives north along the provincial road; the engine fails at the
// authored distance; the car coasts onto the west shoulder and stops; the
// player exits through the driver's door and inspects the wreck. The walk
// phase hands control back to the standard character at the stand point, and
// the mansion approach takes over.

#include "Props/SILIDOpeningCar.h"
#include "Components/StaticMeshComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Player/SILIDCharacter.h"
#include "Systems/SILIDInventoryComponent.h"
#include "Kismet/GameplayStatics.h"

DEFINE_LOG_CATEGORY_STATIC(LogSILIDOpening, Log, All);

namespace
{
	constexpr float M = 100.f; // plan metres -> UE cm

	// Plan-space road centreline — identical to src/world/terrain.js, which
	// the exterior build used to place the road and the car. One truth.
	float RoadCenterPlan(float PlanZ)
	{
		return -62.f + 3.2f * FMath::Sin((PlanZ / M - 10.f) * 0.012f)
			            + 1.4f * FMath::Sin((PlanZ / M) * 0.031f);
	}

	// Analytic height function from src/world/terrain.js, evaluated only on
	// the road corridor where the drive happens (the masks keep the road and
	// its shoulders flat: mansionPad/roadMask flatten to ~0.005 there).
	float HeightOnRoad(float PlanX, float PlanZ)
	{
		const float Rd = PlanX - RoadCenterPlan(PlanZ);
		const float T = 1.f - FMath::Min(1.f, (Rd / 4.6f) * (Rd / 4.6f));
		return 0.05f * FMath::Max(0.f, T);   // the crowned carriageway
	}

	constexpr float STEP_HZ = 30.f;          // prototype fixed-step rate
}

ASILIDOpeningCar::ASILIDOpeningCar()
{
	PrimaryActorTick.bCanEverTick = true;

	Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
	SetRootComponent(Body);

	HoodFocus = CreateDefaultSubobject<UBoxComponent>(TEXT("HoodFocus"));
	IgnitionFocus = CreateDefaultSubobject<UBoxComponent>(TEXT("IgnitionFocus"));
	BootFocus = CreateDefaultSubobject<UBoxComponent>(TEXT("BootFocus"));
	HeadLeft = CreateDefaultSubobject<USpotLightComponent>(TEXT("HeadLeft"));
	HeadRight = CreateDefaultSubobject<USpotLightComponent>(TEXT("HeadRight"));
	HazardLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("HazardLight"));
}

void ASILIDOpeningCar::BeginPlay()
{
	Super::BeginPlay();

	// The build script already parked the wreck at the pull-off. Read the
	// ACTUAL placed transform as the sequence's starting truth, so the state
	// machine and the visible car can never disagree about where the car is.
	const FVector Loc = GetActorLocation();
	X = Loc.X;
	Z = Loc.Y;
	// Build script yaw 90 = facing north (+Y): heading 0 in this class.
	Heading = FMath::DegreesToRadians(GetActorRotation().Yaw - 90.0);
	Speed = 0.f;

	// Focus volumes ride the body in local space (cm): hood ahead, ignition
	// through the windscreen on the driver's side (+X local = left), boot aft.
	HoodFocus->SetBoxExtent(FVector(70.f, 60.f, 60.f));
	HoodFocus->SetRelativeLocation(FVector(240.f, 40.f, 95.f));
	IgnitionFocus->SetBoxExtent(FVector(50.f, 50.f, 50.f));
	IgnitionFocus->SetRelativeLocation(FVector(10.f, 42.f, 100.f));
	BootFocus->SetBoxExtent(FVector(60.f, 60.f, 60.f));
	BootFocus->SetRelativeLocation(FVector(-245.f, 0.f, 100.f));

	// Headlights: 15 m low beams angled down the road.
	for (USpotLightComponent* Spot : { HeadLeft, HeadRight })
	{
		if (!Spot) continue;
		Spot->SetIntensity(3000.f);
		Spot->SetAttenuationRadius(5500.f);
		Spot->SetInnerConeAngle(12.f);
		Spot->SetOuterConeAngle(24.f);
		Spot->SetRelativeRotation(FRotator(-4.f, 0.f, 0.f));
	}
	if (HeadLeft)  HeadLeft->SetRelativeLocation(FVector(236.f, 62.f, 95.f));
	if (HeadRight) HeadRight->SetRelativeLocation(FVector(236.f, -62.f, 95.f));
	if (HazardLight)
	{
		HazardLight->SetIntensity(0.f);
		HazardLight->SetRelativeLocation(FVector(-40.f, 0.f, 115.f));
		HazardLight->SetLightColor(FLinearColor(1.f, 0.6f, 0.16f));
		HazardLight->SetAttenuationRadius(900.f);
	}

	// Headless test hook: -SILIDAUTODRIVE holds full throttle for the whole
	// drive phase, so an unattended -game session can walk the entire opening
	// (drive -> fail -> coast -> stop) and the receipt probe can verify the
	// REAL physics ran — not a forced phase jump. The flag changes nothing
	// about the drive itself; a human pressing W produces the same phases.
	Autodrive = FParse::Param(FCommandLine::Get(), TEXT("SILIDAUTODRIVE"));

	// The game mode decides what happens here: on the exterior map it calls
	// BeginSequence() (the drive); on interior-only starts the wreck simply
	// sits at the shoulder in the walk phase. Default is the roadside walk
	// state so the wreck is always interactable even without a GameMode hook.
	Phase = EOpeningPhase::Stopped;
	UE_LOG(LogSILIDOpening, Log, TEXT("SILID opening car ready at (%.0f, %.0f) heading %.2f - stopped at shoulder"), X, Z, Heading);
}

void ASILIDOpeningCar::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	if (Phase == EOpeningPhase::Idle || Phase == EOpeningPhase::Walk || Phase == EOpeningPhase::Stopped)
	{
		if (Phase == EOpeningPhase::Stopped) StepStopped(DeltaTime);
		return;
	}

	// Fixed-step integration (prototype: 30 Hz, capped backlog).
	// Drive-input staleness: Enhanced Input only fires while a key is being
	// pressed or changed, so a released W stops calling SetDriveInput. If no
	// input has arrived for a few frames the car must coast, not keep the last
	// throttle. 0.15 s covers a dropped frame without cutting a held key.
	if (bHasDirectDriveInput && IsDrivingPhase())
	{
		DriveInputAge += DeltaTime;
		if (DriveInputAge > 0.15f)
		{
			DriveThrottleIn = 0.f;
			DriveSteerIn = 0.f;
			DriveBrakeIn = false;
		}
	}

	const float H = 1.f / STEP_HZ;
	FixedAcc += DeltaTime;
	int32 Steps = 0;
	while (FixedAcc >= H && Steps < 18)
	{
		if (Phase == EOpeningPhase::Driving) StepDrive(H);
		else if (Phase == EOpeningPhase::Failing) StepFail(H);
		FixedAcc -= H;
		++Steps;
	}
	SyncCarTransform();
}

// --------------------------------------------------------------- sequence ---
void ASILIDOpeningCar::SetPhase(EOpeningPhase NewPhase)
{
	Phase = NewPhase;
	const UEnum* Enum = StaticEnum<EOpeningPhase>();
	UE_LOG(LogSILIDOpening, Log, TEXT("SILID opening: phase -> %s"),
		Enum ? *Enum->GetNameStringByValue(static_cast<int64>(NewPhase)) : TEXT("?"));
}

void ASILIDOpeningCar::StepDrive(float Dt)
{
	// Prototype _drive: throttle, brake, steering damping, grade, drag.
	const ASILIDCharacter* Player = Cast<ASILIDCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	bool Throttle = false, Brake = false;
	float SteerIn = 0.f;
	if (bHasDirectDriveInput)
	{
		// Phase 2.2: the controller feeds WASD here directly every frame.
		// This replaces the old GetLastMovementInputVector() read, which never
		// produced throttle in the -game probe (speed=0 with a human driving).
		Throttle = DriveThrottleIn > 0.5f;
		SteerIn  = DriveSteerIn;
		Brake    = DriveBrakeIn;
	}
	else if (Player)
	{
		// Movement input drives the car while seated (the controller routes
		// WASD here when the opening is in the driving phase).
		const FVector Move = Player->GetLastMovementInputVector();
		Throttle = Move.Y > 0.5f;
		Brake = Move.Y < -0.5f;
		SteerIn = -Move.X; // A (+X in plan) steers left = +heading
	}
	if (Autodrive)
	{
		Throttle = true;
	}
	Steer += (SteerIn - Steer) * FMath::Min(1.f, Dt * 5.f);

	if (Throttle && !ThrottleCut)
	{
		const float Room = 1.f - FMath::Max(0.f, Speed) / MaxSpeed;
		Speed += ThrottleAccel * Room * Dt;
	}
	if (Brake)
	{
		if (Speed > 20.f) Speed -= BrakeDecel * Dt;
		else Speed = FMath::Max(-450.f, Speed - 220.f * Dt);
	}
	// rolling resistance
	Speed -= Speed * RollingDrag * Dt;
	if (FMath::Abs(Speed) < 3.f && !Throttle) Speed = 0.f;

	Integrate(Dt, Steer * 0.62f);
	Travelled += FMath::Abs(Speed) * Dt;

	// once-per-second motion receipt: proves the tick runs and shows the
	// actual position/speed in the session log for the headless probes
	DriveLogAcc += Dt;
	if (DriveLogAcc >= 1.f)
	{
		DriveLogAcc = 0.f;
		UE_LOG(LogSILIDOpening, Log, TEXT("SILID opening: drive pos=(%.0f, %.0f) speed=%.0f travelled=%.0f autodrive=%d"),
			X, Z, Speed, Travelled, Autodrive ? 1 : 0);
	}

	const bool ZCondition = Z > TriggerZ;
	if ((Travelled > TriggerDistance && ZCondition) || Travelled > 9500.f || Z > PullZ + 800.f)
		BeginFail();
}

void ASILIDOpeningCar::StepFail(float Dt)
{
	FailT += Dt;

	// Aim at the west shoulder ahead; damp once aligned (prototype _fail).
	const float Lateral = X - (RoadCenterPlan(Z) + PullOffset) * M;
	const float Ahead = FMath::Clamp(Speed, 700.f, 1800.f);
	const float Tz = Z + Ahead;
	const float Tx = (RoadCenterPlan(Tz) + PullOffset) * M;
	float Err = FMath::Atan2(Tx - X, Tz - Z) - Heading;
	if (FMath::Abs(Lateral) < 70.f) Err *= 0.3f;
	const float Guide = FMath::Clamp(Err * 3.f, -1.f, 1.f);
	Steer += (Guide - Steer) * FMath::Min(1.f, Dt * 6.f);

	// A dead engine coasts: no torque, rolling loss + drag. No brakes.
	Speed -= CoastLinear * Dt;
	Speed -= Speed * CoastDrag * Dt;
	if (Speed < 0.f) Speed = 0.f;
	if (Speed < 25.f) { Stop(); return; }

	Integrate(Dt, Steer * 0.75f);

	// Narrative cues at the prototype's timings.
	if (FailT > 0.5f && !CueA)
	{
		CueA = true;
		OnOpeningMessage.Broadcast(NSLOCTEXT("SILID", "OpenFailA",
			"The engine misses. A red light comes on above the wheel."));
	}
	if (FailT > 2.0f && !CueB)
	{
		CueB = true;
		OnOpeningMessage.Broadcast(NSLOCTEXT("SILID", "OpenFailB",
			"You press the pedal. Nothing. The car is slowing itself."));
	}
	if (FailT > 4.5f && !CueC && Speed > 150.f)
	{
		CueC = true;
		OnOpeningMessage.Broadcast(NSLOCTEXT("SILID", "OpenFailC", "Get it off the road."));
	}
}

void ASILIDOpeningCar::StepStopped(float Dt)
{
	DeadT += Dt;
	// the right lamp holds on the battery, then goes (prototype _deadCues)
	const float Right = DeadT < 2.f ? 1.f : FMath::Clamp(1.f - (DeadT - 2.f) / 1.2f, 0.f, 1.f);
	if (HeadRight) HeadRight->SetIntensity(3000.f * Right);
	if (HazardLight)
	{
		HazT += Dt;
		if (DeadT > 1.4f && !HazardsOn) { HazardsOn = true; }
		const bool On = FMath::FloorToInt(HazT * 1.6f) % 2 == 0;
		HazardLight->SetIntensity(HazardsOn && On ? 2800.f : 0.f);
	}
	if (DeadT > 2.2f && !SaidDead)
	{
		SaidDead = true;
		OnOpeningMessage.Broadcast(NSLOCTEXT("SILID", "OpenDead",
			"The engine is dead. It will not catch again."));
	}
}

void ASILIDOpeningCar::BeginFail()
{
	if (Phase != EOpeningPhase::Driving) return;
	SetPhase(EOpeningPhase::Failing);
	FailT = 0.f;
	ThrottleCut = true;
}

void ASILIDOpeningCar::Stop()
{
	SetPhase(EOpeningPhase::Stopped);
	Speed = 0.f;
	DeadT = 0.f;
	bHasDirectDriveInput = false;   // the drive is over: release the controls
	DriveThrottleIn = DriveSteerIn = 0.f;
	DriveBrakeIn = false;
	if (HeadLeft) HeadLeft->SetIntensity(0.f);   // the left lamp dies first
}

void ASILIDOpeningCar::FinishExit()
{
	SetPhase(EOpeningPhase::Walk);
	// Hand control to the on-foot character beside the driver's door.
	// Phase 2.2: also release the drive controls so the controller's gate
	// (IsDrivingPhase) falls through and on-foot movement resumes immediately.
	bHasDirectDriveInput = false;
	DriveThrottleIn = DriveSteerIn = 0.f;
	DriveBrakeIn = false;
	ASILIDCharacter* Player = Cast<ASILIDCharacter>(UGameplayStatics::GetPlayerCharacter(this, 0));
	if (Player)
	{
		const float S = FMath::Sin(Heading), C = FMath::Cos(Heading);
		// stand 1.8 m to the LEFT of the car (driver side, +X local)
		const float StandX = X + C * 180.f;
		const float StandZ = Z - S * 180.f;
		Player->SetActorLocation(FVector(StandX, StandZ, HeightOnRoad(StandX / M, StandZ / M) * M + 88.f), false, nullptr, ETeleportType::TeleportPhysics);
	}
	OnWalkPhaseStarted.Broadcast();
}

// ------------------------------------------------------------ integration ---
void ASILIDOpeningCar::Integrate(float Dt, float YawRate)
{
	const float Dir = Speed >= 0.f ? 1.f : -1.f;
	const float Rate = YawRate * FMath::Min(1.f, FMath::Abs(Speed) / 500.f) * Dir;
	Heading += Rate * Dt;
	const float Nx = X + FMath::Sin(Heading) * Speed * Dt;
	const float Nz = Z + FMath::Cos(Heading) * Speed * Dt;
	const float Gy = HeightOnRoad(X / M, Z / M) * M;
	if (CarBlocked(Nx, Nz, Gy))
	{
		Speed *= -0.12f;   // a tree, a bank: the car stops being a car
		return;
	}
	X = Nx; Z = Nz; Heading = Heading;
}

bool ASILIDOpeningCar::CarBlocked(float Nx, float Nz, float Gy) const
{
	// Six probe points around the car (front corners, rear corners, nose, tail).
	// Both arrays must have six entries — a length mismatch here reads
	// out-of-bounds values and blocks the car on phantom obstacles.
	const float S = FMath::Sin(Heading), C = FMath::Cos(Heading);
	const float Lx[6] = { 95.f, -95.f, 95.f, -95.f, 0.f, 0.f };
	const float Lz[6] = { 230.f, 230.f, -230.f, -230.f, 270.f, -270.f };
	for (int32 i = 0; i < 6; ++i)
	{
		const float Px = Nx + Lx[i] * C + Lz[i] * S;
		const float Pz = Nz - Lx[i] * S + Lz[i] * C;
		if (FMath::Abs(Px - RoadCenterPlan(Pz) * M) < 460.f) continue; // still on tarmac
		// anything beyond the shoulder blocks: a bank too steep to climb
		const float H2 = HeightOnRoad(Px / M, Pz / M) * M;
		if (H2 - Gy > 50.f) return true;
	}
	return false;
}

float ASILIDOpeningCar::HeightAtPlan(float PlanX, float PlanZ) const
{
	return HeightOnRoad(PlanX, PlanZ) * M;
}

float ASILIDOpeningCar::RoadCenter(float PlanZ) const
{
	return RoadCenterPlan(PlanZ) * M;
}

void ASILIDOpeningCar::SyncCarTransform()
{
	// Pose the wreck on the road: pitch/roll follow the crown and grade.
	const float Gy = HeightOnRoad(X / M, Z / M) * M;
	const float Front = HeightOnRoad((X + FMath::Sin(Heading) * 160.f) / M,
	                                 (Z + FMath::Cos(Heading) * 160.f) / M) * M
			          - HeightOnRoad((X - FMath::Sin(Heading) * 160.f) / M,
			                         (Z - FMath::Cos(Heading) * 160.f) / M) * M;
	const float Right = HeightOnRoad((X + FMath::Cos(Heading) * 95.f) / M,
	                                  (Z - FMath::Sin(Heading) * 95.f) / M) * M
			          - HeightOnRoad((X - FMath::Cos(Heading) * 95.f) / M,
			                         (Z + FMath::Sin(Heading) * 95.f) / M) * M;
	SetActorLocation(FVector(X, Z, Gy));
	SetActorRotation(FRotator(-FMath::RadiansToDegrees(FMath::Atan2(Front, 320.f)),
		                      90.f + FMath::RadiansToDegrees(Heading),
		                      FMath::RadiansToDegrees(FMath::Atan2(Right, 190.f))));
}

// ------------------------------------------------------------ interaction ---
bool ASILIDOpeningCar::CanInteract(const ASILIDCharacter* Player) const
{
	// The roadside checks only exist once the wreck has stopped.
	return Phase == EOpeningPhase::Stopped || Phase == EOpeningPhase::Walk;
}

FText ASILIDOpeningCar::GetInteractionText(const ASILIDCharacter* Player) const
{
	if (!HoodChecked)  return NSLOCTEXT("SILID", "CarHood", "check the engine");
	if (!RestartTried) return NSLOCTEXT("SILID", "CarIgnition", "try the key");
	if (!BootChecked)  return NSLOCTEXT("SILID", "CarBoot", "open the trunk");
	return NSLOCTEXT("SILID", "CarDone", "the wreck has nothing more to give");
}

bool ASILIDOpeningCar::Interact(ASILIDCharacter* Player)
{
	if (!(Phase == EOpeningPhase::Stopped || Phase == EOpeningPhase::Walk))
		return false;
	// Route on the player's aim height relative to the car: the roadside
	// checks are three points on one actor, and the character's focus trace
	// reports the actor, not the sub-component — so pick the zone whose focus
	// point is nearest to the aim direction.
	static const FText HoodFirst = NSLOCTEXT("SILID", "HoodFirst",
		"The auxiliary belt is shredded to wires, and the block is wet with oil. "
		"There is nothing in this car that can mend it.");
	static const FText HoodAgain = NSLOCTEXT("SILID", "HoodAgain",
		"Shredded belt. Oil. Nothing here you can use.");
	static const FText IgnitionText = NSLOCTEXT("SILID", "Ignition",
		"You reach in and turn the key. The starter clicks once — weak — and gives up.");
	static const FText IgnitionAgain = NSLOCTEXT("SILID", "Ignition2",
		"One dry click. It is not coming back.");
	static const FText BootFirst = NSLOCTEXT("SILID", "BootFirst",
		"A jacket. A half-case of water. A charger. Nothing here that can mend a belt.");
	static const FText BootAgain = NSLOCTEXT("SILID", "BootAgain",
		"Water, a jacket, a charger.");

	const FVector Eye = Player->GetActorLocation() + FVector(0, 0, 60.f);
	const FVector Aim = Player->GetActorForwardVector();
	struct FZone { FVector Point; bool* Flag; const FText* First; const FText* Again; };
	const FZone Zones[3] = {
		{ HoodFocus     ? HoodFocus->GetComponentLocation()     : FVector(), &HoodChecked,  &HoodFirst,     &HoodAgain },
		{ IgnitionFocus ? IgnitionFocus->GetComponentLocation() : FVector(), &RestartTried, &IgnitionText,  &IgnitionAgain },
		{ BootFocus     ? BootFocus->GetComponentLocation()     : FVector(), &BootChecked,  &BootFirst,     &BootAgain },
	};
	float BestScore = -1.f;
	int32 BestZone = INDEX_NONE;
	for (int32 i = 0; i < 3; ++i)
	{
		const FVector To = Zones[i].Point - Eye;
		const float Dist = To.Size();
		if (Dist > 320.f) continue;
		const float Dot = FVector::DotProduct(Aim, To.GetSafeNormal());
		if (Dot < 0.35f) continue;
		const float Score = Dot * 2.f - Dist * 0.002f;
		if (Score > BestScore) { BestScore = Score; BestZone = i; }
	}
	if (BestZone == INDEX_NONE) return false;

	if (Zones[BestZone].Flag == &RestartTried)
	{
		RestartTried = true;
		OnOpeningMessage.Broadcast(*Zones[BestZone].First);
		return true;
	}
	if (*Zones[BestZone].Flag)
	{
		OnOpeningMessage.Broadcast(*Zones[BestZone].Again);
	}
	else
	{
		*Zones[BestZone].Flag = true;
		OnOpeningMessage.Broadcast(*Zones[BestZone].First);
	}
	return true;
}

void ASILIDOpeningCar::OnFocus() {}
void ASILIDOpeningCar::OnUnfocus() {}

FText ASILIDOpeningCar::GetExamineText(const ASILIDCharacter* Player) const
{
	return NSLOCTEXT("SILID", "CarExamine",
		"Del's SUV. The auxiliary belt went, and the engine with it. The roadside is empty in both directions.");
}

void ASILIDOpeningCar::ForceBreakdown()
{
	if (Phase == EOpeningPhase::Driving) BeginFail();
}

void ASILIDOpeningCar::SetDriveInput(float ThrottleAxis, float SteerAxis, bool bBrake)
{
	// Only the live drive consumes input; the controller's gate checks the
	// phase too, but this is the authoritative guard (Stop/FinishExit clear it).
	if (!IsDrivingPhase())
	{
		bHasDirectDriveInput = false;
		return;
	}
	DriveThrottleIn = FMath::Clamp(ThrottleAxis, -1.f, 1.f);
	DriveSteerIn    = FMath::Clamp(SteerAxis, -1.f, 1.f);
	DriveBrakeIn    = bBrake;
	bHasDirectDriveInput = true;
	DriveInputAge = 0.f;
}

void ASILIDOpeningCar::BeginSequence()
{
	// Drive starts from where BeginPlay parked the wreck: rewind to the
	// authored start point on the road (plan z = -78, northbound lane) with
	// Del facing down the road. The failure then triggers at the scripted
	// distance, exactly as the prototype's opening.js does.
	constexpr float StartZ = -7800.f;   // plan -78 m
	constexpr float StartLane = 1.7f;   // 1.7 m northbound lane offset (METRES:
	                                    // added inside the metres expression below)
	X = (RoadCenterPlan(StartZ / M) + StartLane) * M;
	Z = StartZ;
	Heading = 0.f;
	Speed = 0.f;
	Steer = 0.f;
	Travelled = 0.f;
	ThrottleCut = false;
	SaidDead = false;
	CueA = CueB = CueC = false;
	bHasDirectDriveInput = false;   // stale frame input from a previous run
	DriveThrottleIn = DriveSteerIn = 0.f;
	DriveBrakeIn = false;
	SetPhase(EOpeningPhase::Driving);
	OnOpeningMessage.Broadcast(NSLOCTEXT("SILID", "DriveStart", "Drive. The road is empty."));
	UE_LOG(LogSILIDOpening, Log, TEXT("SILID opening: drive begun at (%.0f, %.0f)"), X, Z);
}
